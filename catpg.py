# this is a KISS wrapper i made for asyncpg
# it will eventually be a separate thing once its good enough

import asyncpg

conn = None


async def connect(**kwargs):
    global conn
    conn = await asyncpg.connect(**kwargs)


async def close():
    await conn.close()


class Model:
    _primary_key = "id"
    _capped_ints = []

    def __init__(self, record):
        # init model from asyncpg Record
        self.__dirty_values = []
        self.__values = dict(record.items())

    # setter sugar
    def __setattr__(self, name, value):
        if name[0] == "_":
            return super().__setattr__(name, value)
        self.__setitem__(name, value)

    def __setitem__(self, name, value):
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
    def __getattr__(self, name):
        if name[0] == "_":
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        return self.__values[name]

    def __getitem__(self, name):
        if name[0] == "_":
            return super().__getitem__(name)
        return self.__values[name]

    async def delete(self):
        table = self.__class__.__name__.lower()
        query_string = f'DELETE FROM "{table}" WHERE {self._primary_key} = $1;'
        await conn.execute(query_string, self.__values[self._primary_key])
        self.__dirty_values = []
        self.__values = []

    async def save(self):
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
    async def _get(self, fields=None, **kwargs):
        table = self.__name__.lower()
        select = "*"
        if fields:
            if self._primary_key not in fields:
                fields.append(self._primary_key)
            select = ", ".join(f'"{i}"' for i in fields)
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

    async def refresh_from_db(self):
        args = {self._primary_key: self.__values[self._primary_key]}
        result = await self._get(**args)
        self.__init__(result)

    @classmethod
    async def get_or_none(self, fields=None, **kwargs):
        try:
            result = await self._get(fields, **kwargs)
            return self(result)
        except Exception:
            return None

    @classmethod
    async def get_or_create(self, **kwargs):
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
    async def create(self, **kwargs):
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
    async def filter(self, filter=None, *args, **kwargs):
        table = self.__name__.lower()
        async with conn.transaction():
            select = "*"
            if "fields" in kwargs:
                if self._primary_key not in kwargs["fields"]:
                    kwargs["fields"].append(self._primary_key)
                select = ", ".join(f'"{i}"' for i in kwargs["fields"])
            query = f'SELECT {select} FROM "{table}"'
            if filter:
                query += f" WHERE {filter}"
            cur = await conn.fetch(query + ";", *args)
            for row in cur:
                val = {self._primary_key: row[self._primary_key]}
                if "fields" in kwargs:
                    row = await self.get_or_none(kwargs["fields"], **val)
                else:
                    row = await self.get_or_none(**val)
                if not row:
                    continue
                yield row

    @classmethod
    async def limit(self, fields, filter=None, *args):
        async for row in self.filter(filter, *args, fields=fields):
            yield row

    @classmethod
    async def all(self):
        async for row in self.filter():
            yield row

    @classmethod
    async def collect(self, filter=None, *args):
        return [i async for i in self.filter(filter, *args)]

    @classmethod
    async def __do_function(self, func, column, filter=None, *args):
        table = self.__name__.lower()
        if column != "*":
            column = f'"{column}"'
        query = f'SELECT {func}({column}) FROM "{table}"'
        if filter:
            query += f" WHERE {filter}"
        return await conn.fetchval(query + ";", *args)

    @classmethod
    async def sum(self, column, filter=None, *args):
        return await self.__do_function("SUM", column, filter, *args) or 0

    @classmethod
    async def max(self, column, filter=None, *args):
        return await self.__do_function("MAX", column, filter, *args)

    @classmethod
    async def min(self, column, filter=None, *args):
        return await self.__do_function("MIN", column, filter, *args)

    @classmethod
    async def count(self, filter=None, *args):
        return await self.__do_function("COUNT", "*", filter, *args)

    @classmethod
    async def bulk_update(self, rows, *columns):
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
