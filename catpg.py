# MIT License
#
# Copyright (c) 2025 Lia Milenakos
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# this is a KISS wrapper i made for asyncpg

import asyncpg
from typing import Any, AsyncGenerator, TypeVar

conn = None


async def connect(**kwargs):
    global conn
    conn = await asyncpg.connect(**kwargs)


async def close():
    if conn:
        await conn.close()


# this is used in limit() to distinguish between raw SQL and column names
class RawSQL(str):
    pass


ModelInstance = TypeVar("ModelInstance", bound="Model")


class Model:
    _primary_key = "id"
    _capped_ints = []

    def __init__(self, record: asyncpg.Record):
        # init model from asyncpg Record
        self.__dirty_values = []
        self.__values = dict(record.items())

    # setter sugar
    def __setattr__(self, name: str, value) -> None:
        if name[0] == "_":
            return super().__setattr__(name, value)
        self.__setitem__(name, value)

    def __setitem__(self, name: str, value) -> None:
        if name[0] == "_":
            return super().__setitem__(name, value)
        if name in self.__values:
            if value != self.__values[name] and name not in self.__dirty_values:
                self.__dirty_values.append(name)

            if name in self._capped_ints:
                self.__values[name] = max(-2147483648, min(2147483647, value))
            else:
                self.__values[name] = value

    # getter sugar
    def __getattr__(self, name: str) -> Any:
        if name[0] == "_":
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        return self.__values[name]

    def __getitem__(self, name: str) -> Any:
        if name[0] == "_":
            return super().__getitem__(name)
        return self.__values[name]

    async def delete(self) -> None:
        table = self.__class__.__name__.lower()
        query_string = f'DELETE FROM "{table}" WHERE {self._primary_key} = $1;'
        await conn.execute(query_string, self.__values[self._primary_key])
        self.__dirty_values = []
        self.__values = []

    async def save(self) -> None:
        table = self.__class__.__name__.lower()
        if not self.__dirty_values:
            return
        query_string = f'UPDATE "{table}" SET '
        args = []
        var_counter = 1

        # write dirty fields
        changes = []
        for i in self.__dirty_values:
            changes.append(f'"{i}" = ${var_counter}')
            args.append(self.__values[i])
            var_counter += 1
        query_string += ", ".join(changes)

        # show where to write
        query_string += f" WHERE {self._primary_key} = ${var_counter};"
        args.append(self.__values[self._primary_key])

        # run the query
        await conn.execute(query_string, *args)
        self.__dirty_values = []

    @classmethod
    async def _get(self, fields: None | list[str | RawSQL] = None, **kwargs) -> ModelInstance:
        table = self.__name__.lower()
        select = "*"
        if fields:
            if self._primary_key not in fields:
                fields.append(self._primary_key)
            select = ", ".join(i if isinstance(i, RawSQL) else f'"{i}"' for i in fields)
        query_string = f'SELECT {select} FROM "{table}" WHERE '
        var_counter = 1

        # add the search parameters
        changes = []
        for i in kwargs.keys():
            changes.append(f'"{i}" = ${var_counter}')
            var_counter += 1
        query_string += " AND ".join(changes) + " LIMIT 1;"

        # run the query
        return await conn.fetchrow(query_string, *kwargs.values())

    async def refresh_from_db(self) -> None:
        args = {self._primary_key: self.__values[self._primary_key]}
        result = await self._get(**args)
        self.__init__(result)

    @classmethod
    async def get(self, fields: None | list[str | RawSQL] = None, **kwargs) -> ModelInstance:
        result = await self._get(fields=fields, **kwargs)
        return self(result)

    @classmethod
    async def get_or_none(self, fields: None | list[str | RawSQL] = None, **kwargs) -> ModelInstance | None:
        try:
            return await self.get(fields=fields, **kwargs)
        except asyncpg.exceptions.PostgresError:
            return None

    @classmethod
    async def get_or_create(self, **kwargs) -> ModelInstance:
        table = self.__name__.lower()
        values = kwargs.values()

        # create if doesnt exist

        query_string = f'INSERT INTO "{table}" ('
        var_counter = 1

        # add the search parameters
        changes = []
        for i in kwargs.keys():
            changes.append(i)
            var_counter += 1
        query_string += ", ".join(changes) + ") VALUES ("

        # add the var numbers
        changes2 = ["$" + str(i) for i in range(1, var_counter)]
        query_string += ", ".join(changes2)

        query_string += ") ON CONFLICT (" + ", ".join(changes) + ") DO NOTHING;"

        # run the query
        await conn.execute(query_string, *values)

        # get
        result = await self._get(**kwargs)
        return self(result)

    @classmethod
    async def create(self, **kwargs) -> None:
        table = self.__name__.lower()
        values = kwargs.values()

        query_string = f'INSERT INTO "{table}" ('
        var_counter = 1

        # add the search parameters
        changes = []
        for i in kwargs.keys():
            changes.append(i)
            var_counter += 1
        query_string += ", ".join(changes) + ") VALUES ("

        # add the var numbers
        changes2 = ["$" + str(i) for i in range(1, var_counter)]
        query_string += ", ".join(changes2) + ");"
        await conn.execute(query_string, *values)

    @classmethod
    async def filter(self, filter: str | RawSQL | None = None, *args, **kwargs) -> AsyncGenerator[ModelInstance]:
        table = self.__name__.lower()
        select = "*"
        if "fields" in kwargs:
            if self._primary_key not in kwargs["fields"]:
                kwargs["fields"].append(self._primary_key)
            select = ", ".join(i if isinstance(i, RawSQL) else f'"{i}"' for i in kwargs["fields"])
        query = f'SELECT {select} FROM "{table}"'
        if filter:
            query += f" WHERE {filter}"
        cur = await conn.fetch(query + ";", *args)
        for row in cur:
            val = {self._primary_key: row[self._primary_key]}
            if "fields" in kwargs:
                row = await self.get_or_none(fields=kwargs["fields"], **val)
            else:
                row = await self.get_or_none(**val)
            if not row:
                continue
            yield row

    @classmethod
    async def limit(self, fields: str | RawSQL | None | list[str | RawSQL] = None, filter: str | RawSQL | None = None, *args) -> AsyncGenerator[ModelInstance]:
        if isinstance(fields, str):
            fields = [fields]
        async for row in self.filter(filter, *args, fields=fields):
            yield row

    @classmethod
    async def all(self) -> AsyncGenerator[ModelInstance]:
        async for row in self.filter():
            yield row

    @classmethod
    async def collect(self, filter: str | RawSQL | None = None, *args) -> list[ModelInstance]:
        return [i async for i in self.filter(filter, *args)]

    @classmethod
    async def collect_limit(self, fields: str | RawSQL | None | list[str | RawSQL] = None, filter: str | RawSQL | None = None, *args) -> list[ModelInstance]:
        return [i async for i in self.limit(fields, filter, *args)]

    @classmethod
    async def __do_function(self, func: str, column: str, filter: str | RawSQL | None = None, *args) -> Any:
        table = self.__name__.lower()
        if column != "*":
            column = f'"{column}"'
        query = f'SELECT {func}({column}) FROM "{table}"'
        if filter:
            query += f" WHERE {filter}"
        return await conn.fetchval(query + ";", *args)

    @classmethod
    async def sum(self, column: str, filter: str | RawSQL | None = None, *args) -> int:
        return await self.__do_function("SUM", column, filter, *args) or 0

    @classmethod
    async def max(self, column: str, filter: str | RawSQL | None = None, *args) -> int:
        return await self.__do_function("MAX", column, filter, *args)

    @classmethod
    async def min(self, column: str, filter: str | RawSQL | None = None, *args) -> int:
        return await self.__do_function("MIN", column, filter, *args)

    @classmethod
    async def count(self, filter: str | RawSQL | None = None, *args) -> int:
        return await self.__do_function("COUNT", "*", filter, *args)

    @classmethod
    async def bulk_update(self, rows: list[ModelInstance], *columns) -> None:
        table = self.__name__.lower()
        # build the query
        query = f'UPDATE "{table}" SET '
        var_counter = 1
        change = []
        for col in columns:
            change.append(f"{col} = ${var_counter}")
            var_counter += 1
        query += ", ".join(change) + f" WHERE {self._primary_key} = ${var_counter};"

        # prepare the data
        data = []
        for row in rows:
            curr = []
            for col in columns:
                curr.append(row[col])
            curr.append(row[self._primary_key])
            data.append(tuple(curr))

        # execute the query
        await conn.executemany(query, data)
