# MIT License
#
# Copyright (c) 2026 Lia Milenakos
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

from typing import Any, AsyncGenerator, TypeVar

import asyncpg

pool = None


async def connect(**kwargs):
    global pool
    pool = await asyncpg.create_pool(**kwargs)


async def close():
    if pool:
        await pool.close()


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
        await pool.execute(query_string, self.__values[self._primary_key])
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
        await pool.execute(query_string, *args)
        self.__dirty_values = []

    @classmethod
    async def _get(cls, fields: None | list[str | RawSQL] = None, **kwargs) -> asyncpg.Record:
        table = cls.__name__.lower()
        select = "*"
        if fields:
            if cls._primary_key not in fields:
                fields.append(cls._primary_key)
            select = ", ".join(i if i.__class__.__name__ == "RawSQL" else f'"{i}"' for i in fields)
        query_string = f'SELECT {select} FROM "{table}" WHERE '
        var_counter = 1

        # add the search parameters
        changes = []
        for i in kwargs.keys():
            changes.append(f'"{i}" = ${var_counter}')
            var_counter += 1
        query_string += " AND ".join(changes) + " LIMIT 1;"

        # run the query
        return await pool.fetchrow(query_string, *kwargs.values())

    async def refresh_from_db(self) -> None:
        args = {self._primary_key: self.__values[self._primary_key]}
        result = await self._get(**args)
        if result:
            self.__init__(result)

    @classmethod
    async def get(cls, fields: None | list[str | RawSQL] = None, **kwargs) -> ModelInstance:
        result = await cls._get(fields=fields, **kwargs)
        return cls(result)

    @classmethod
    async def get_or_none(cls, fields: None | list[str | RawSQL] = None, **kwargs) -> ModelInstance | None:
        try:
            return await cls.get(fields=fields, **kwargs)
        except asyncpg.exceptions.PostgresError:
            return None
        except AttributeError:
            return None

    @classmethod
    async def get_or_create(cls, **kwargs) -> ModelInstance:
        table = cls.__name__.lower()
        values = kwargs.values()

        # build column names and placeholders
        columns = list(kwargs.keys())
        column_names = ", ".join(f'"{col}"' for col in columns)
        placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))

        # build the upsert updates (no-op updates to trigger RETURNING)
        updates = ", ".join(f'"{col}" = EXCLUDED."{col}"' for col in columns)

        # single query: insert or update (with same values) and return
        query_string = f'INSERT INTO "{table}" ({column_names}) VALUES ({placeholders}) ON CONFLICT ({column_names}) DO UPDATE SET {updates} RETURNING *;'

        # run the query and return the result
        result = await pool.fetchrow(query_string, *values)
        return cls(result)

    @classmethod
    async def create(cls, **kwargs) -> None:
        table = cls.__name__.lower()
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
        await pool.execute(query_string, *values)

    @classmethod
    async def filter(
        cls, filter: str | RawSQL | None = None, *args, refetch: bool = True, add_primary_key: bool = True, **kwargs
    ) -> AsyncGenerator[ModelInstance, None]:
        table = cls.__name__.lower()
        select = "*"
        if "fields" in kwargs:
            if add_primary_key and cls._primary_key not in kwargs["fields"]:
                kwargs["fields"].append(cls._primary_key)
            select = ", ".join(i if i.__class__.__name__ == "RawSQL" else f'"{i}"' for i in kwargs["fields"])
        query = f'SELECT {select} FROM "{table}"'
        if filter:
            query += f" WHERE {filter}"
        cur = await pool.fetch(query + ";", *args)
        for row in cur:
            if refetch:
                val = {cls._primary_key: row[cls._primary_key]}
                if "fields" in kwargs:
                    row = await cls.get_or_none(fields=kwargs["fields"], **val)
                else:
                    row = await cls.get_or_none(**val)
                if not row:
                    continue
            else:
                row = cls(row)
            yield row

    @classmethod
    async def limit(
        cls,
        fields: str | RawSQL | None | list[str | RawSQL] = None,
        filter: str | RawSQL | None = None,
        *args,
        refetch: bool = True,
        add_primary_key: bool = True,
    ) -> AsyncGenerator[ModelInstance, None]:
        if isinstance(fields, str):
            fields = [fields]
        async for row in cls.filter(filter, refetch=refetch, add_primary_key=add_primary_key, *args, fields=fields):
            yield row

    @classmethod
    async def all(cls) -> AsyncGenerator[ModelInstance, None]:
        async for row in cls.filter():
            yield row

    @classmethod
    async def collect(cls, filter: str | RawSQL | None = None, *args, add_primary_key: bool = True) -> list[ModelInstance]:
        return [i async for i in cls.filter(filter, *args, refetch=False, add_primary_key=add_primary_key)]

    @classmethod
    async def collect_limit(
        cls, fields: str | RawSQL | None | list[str | RawSQL] = None, filter: str | RawSQL | None = None, *args, add_primary_key: bool = True
    ) -> list[ModelInstance]:
        return [i async for i in cls.limit(fields, filter, *args, refetch=False, add_primary_key=add_primary_key)]

    @classmethod
    async def __do_function(cls, func: str, column: str, filter: str | RawSQL | None = None, *args) -> Any:
        table = cls.__name__.lower()
        if column != "*":
            column = f'"{column}"'
        query = f'SELECT {func}({column}) FROM "{table}"'
        if filter:
            query += f" WHERE {filter}"
        return await pool.fetchval(query + ";", *args)

    @classmethod
    async def sum(cls, column: str, filter: str | RawSQL | None = None, *args) -> int:
        return await cls.__do_function("SUM", column, filter, *args) or 0

    @classmethod
    async def max(cls, column: str, filter: str | RawSQL | None = None, *args) -> int:
        return await cls.__do_function("MAX", column, filter, *args)

    @classmethod
    async def min(cls, column: str, filter: str | RawSQL | None = None, *args) -> int:
        return await cls.__do_function("MIN", column, filter, *args)

    @classmethod
    async def count(cls, filter: str | RawSQL | None = None, *args) -> int:
        return await cls.__do_function("COUNT", "*", filter, *args)

    @classmethod
    async def bulk_update(cls, rows: list[ModelInstance], *columns) -> None:
        table = cls.__name__.lower()
        # build the query
        query = f'UPDATE "{table}" SET '
        var_counter = 1
        change = []
        for col in columns:
            change.append(f"{col} = ${var_counter}")
            var_counter += 1
        query += ", ".join(change) + f" WHERE {cls._primary_key} = ${var_counter};"

        # prepare the data
        data = []
        for row in rows:
            curr = []
            for col in columns:
                curr.append(row[col])
            curr.append(row[cls._primary_key])
            data.append(tuple(curr))

        # execute the query
        await pool.executemany(query, data)
