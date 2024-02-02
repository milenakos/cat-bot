# by Marwynn Somridhivej at https://gitlab.com/marwynnsomridhivej/dpy-http-server/
# modified by Milenakos to work with nextcord

import asyncio
import functools
import inspect
from typing import Callable, Iterator, List, Union

from aiohttp import web
from nextcord.ext.commands import AutoShardedBot

_HTTP_METHODS = frozenset([
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
])
_ROUTES: List["RouteDef"] = []


class DuplicateRouteError(ValueError):
    pass


class ServerAlreadyRunning(Exception):
    pass


class ServerNotRunning(Exception):
    pass


class NoServerFound(AttributeError):
    pass


class RouteDef(object):
    """A wrapper object that stores information about a route

    Parameters
    ------
    path :class:`str`
        - The path of the route
    method :class:`str`
        - The HTTP method to use for this route
    handler :class:Union[`Callable`, `str`]
        - The async function to use as the handler or its string name
        - This function, or its resolved function, must be a coroutine function
    cog :class:`str`
        - The cog this route is associated with, if applicable. Defaults to :type:`None`
    """
    __slots__ = [
        "_path",
        "_method",
        "_handler",
        "_cog",
    ]

    def __init__(self, path: str, method: str, handler: Union[Callable, str], cog: Union[str, None]) -> None:
        if not path.startswith("/"):
            raise ValueError("Specified route must begin with a forwards slash \"/\"")
        self._path = path
        if method.upper() not in _HTTP_METHODS:
            raise ValueError(f"Route method must be either {', '.join(_HTTP_METHODS)}, not {method.upper()}")
        self._method = method.lower()
        if isinstance(handler, Callable) and not asyncio.iscoroutinefunction(handler):
            raise TypeError(f"A callable handler must be a coroutine")
        self._handler = handler
        self._cog = cog

    def __eq__(self, other: "RouteDef") -> bool:
        return self.path == other.path and self.method == other.method

    def __ne__(self, other: "RouteDef") -> bool:
        return not self == other

    @property
    def path(self) -> str:
        return self._path

    @property
    def method(self) -> str:
        return self._method

    @property
    def handler(self) -> str:
        return self._handler

    @property
    def cog(self) -> str:
        return self._cog


class RouteTable(object):
    """A wrapper object containing all the routes to be added to the HTTPServer application

    Parameters
    ------
    routes :class:List[:class:`RouteDef`]
        - The list of routes to initialise the internal routes list with
    """
    __slots__ = [
        "_routes"
    ]

    def __init__(self, routes: List[RouteDef] = []) -> None:
        self._routes = []
        for route in routes:
            self.append(route_def=route)

    def __iter__(self) -> Iterator[RouteDef]:
        for route in self._routes:
            yield route

    @property
    def routes(self) -> List[RouteDef]:
        return self._routes

    def append(self, route_def: RouteDef = None, path: str = None,
               method: str = None, handler: Union[Callable, str] = None,
               cog: Union[str, None] = None,) -> None:
        """Append a new route to the internal list of RouteDefs

        Parameters
        ------
        route_def :class:Optional[:class:`RouteDef`]
            - The RouteDef object to append. Defaults to :type:`None`
        path :class:Optional[`str`]
            - The route's path. Defaults to :type:`None`
        method :class:Optional[`str`]
            - The HTTP method to use. Defaults to :type:`None`
        handler :class:Union[`Callable`, `str`]
            - The handler function or string that corresponds to a function defined in the :class:`AutoShardedBot` instance. Defaults to :type:`None`
        cog :class:`str`
            - The cog this function is associated with, if applicable. Defaults to :type:`None`

        Raises:
            :exc:`DuplicateRouteError`
                - A route with the same path and method is already added
        """
        if not route_def:
            route_def = RouteDef(path, method, handler, cog)
        if any(route_def == route for route in self):
            raise DuplicateRouteError(
                f"A route with route {route_def.path} and method {route_def.method} already exists")
        self._routes.append(route_def)


class HTTPServer:
    """The HTTP Server to be used in conjunction with the bot instance itself

    Parameters
    ------
    bot :class:`AutoShardedBot`
        - The bot instance to associate this :class:`HTTPServer` with
    host :class:`str`
        - The host to bind to
    port :class:`int`
        - The port to listen on
    routes :class:Optional[List[:class:`RouteDef`]]
        - A list of :class:`RouteDef` containing predefined routes. Defaults to `[]`
    """
    __slots__ = [
        "_bot",
        "_host",
        "_port",
        "_routes",
        "_web",
        "_runner",
        "_site",
        "_is_running",
        "_start_fut",
        "_stop_fut",
    ]

    def __init__(self, *, bot, host: str, port: int, routes: List[RouteDef] = []) -> None:
        self._bot: AutoShardedBot = bot
        self._host = host or "0.0.0.0"
        self._port = port or 8000
        self._routes: RouteTable = RouteTable(routes)
        self._web = web.Application(loop=self._bot.loop)
        self._runner: web.AppRunner = None
        self._site: web.TCPSite = None
        self._is_running = False
        self._start_fut: asyncio.Future = self._bot.loop.create_future()
        self._stop_fut: asyncio.Future = self._bot.loop.create_future()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def web(self) -> web.Application:
        return self._web

    def _add_route(self, path: str, method: str, handler: Callable) -> None:
        return self._routes.append(path=path, method=method, handler=handler)

    def _add_routes_to_web(self) -> None:
        _routes = []
        for route in _ROUTES:
            self._routes.append(route_def=route)
        _ROUTES.clear()
        for route in self._routes:
            _method: Callable = getattr(web, route.method)
            _source = self._bot.get_cog(route.cog) or self._bot
            _handler = getattr(_source, route.handler) if isinstance(route.handler, str) else route.handler
            _sig = inspect.signature(_handler)
            args = []
            kwargs = {}
            if _sig.parameters.get("args") and _sig.parameters.get("kwargs"):
                kwargs["_bot_or_cog_self__"] = _source
            if _sig.parameters.get("self", None):
                args.append(_source)
            _handler = functools.partial(_handler, *args, **kwargs)
            _routes.append(_method(route.path, _handler))
        self._web.add_routes(_routes)

    def add_route(self, *, path: str, method: str, cog: Union[str, None] = None) -> Callable:
        """Decorator helper method used to register routes to the HTTPServer instance

        Parameters
        ------
        path :class:`str`
            - The path of the route
        method :class:`str`
            - The HTTP method to be used for this route
        cog :class:`str`
            - The cog this decorator is applied in, if applicable. Defaults to :type:`None`
        """
        def decorator(func: Callable):
            return self._add_route(path, method, func, cog)
        return decorator

    async def start(self) -> None:
        """Starts the HTTPServer instance

        Raises
        ------
        :exc:`ServerAlreadyRunning`
            - The HTTPServer instance has been started and is already running
        """
        if self._is_running:
            raise ServerAlreadyRunning("The current instance of the server has already been started")
        self._add_routes_to_web()
        self._runner = web.AppRunner(self._web)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self._host, port=self._port)
        await self._site.start()
        self._is_running = True
        self._start_fut.set_result(True)
        print(f"HTTP SERVER STARTED, LISTENING ON {self.host}:{self.port}")

    async def stop(self) -> None:
        """Gracefully shutdown the running HTTPServer instance

        Raises
        ------
        :exc:`ServerNotRunning`
            - The HTTPServer instance has not been started and cannot be shutdown
        """
        if not self._is_running:
            raise ServerNotRunning("The current instance has not been started and cannot be shutdown")
        await self._site.stop()
        await self._runner.shutdown()
        self._stop_fut.set_result(True)

    async def wait_until_start(self) -> None:
        """Waits until the server has started
        """
        return await self._start_fut

    async def wait_until_stop(self) -> None:
        """Waits until the server has stopped
        """
        return await self._stop_fut


def add_route(*, path: str, method: str, cog: str = None) -> Callable:
    """Decorator helper method used to register routes to the HTTPServer instance
    attached to the :class:`AutoShardedBot` instance. It does so by finding
    the HTTPServer instance and calls its :meth:`add_route` method

    Parameters
    ------
    path :class:`str`
        - The path of the route
    method :class:`str`
        - The HTTP method to be used for this route
    cog :class:`str`
        - The cog this decorator is applied in, if applicable. Defaults to :type:`None`
    """
    def decorator(func: Callable):
        return _ROUTES.append(RouteDef(path, method, func, cog))
    return decorator


def check(*, predicate: Union[Callable, str], fail_handler: Union[Callable, str]) -> Callable:
    """Decorator helper method used to validate requests before data is processed
    by the wrapped handler function itself. This decorator should always
    be placed below any `@add_route` decorator

    Parameters
    ------
    predicate :class:Union[`Callable`, `str`]
        - The function to use as a check
        - If passed in :class:`str`, will search for a function
        from the :param:`self` of the handler. Only pass in a :class:`str`
        when using a check defined in the same class
        - Receives only the :param:`request` (:class:`web.Request`) parameter
        - Must be asynchronous (defined using `async def`)
        - Should return :class:`bool`. :param:`fail_handler` will be called
        if result of the predicate is `False`
    fail_handler :class:Union[`Callable`, `str`]
        - The function that handles when a check has failed
        - If passed in :class:`str`, will search for a function
        from the :param:`self` of the handler. Only pass in a :class:`str`
        when using a check defined in the same class
        - Receives only the :param:`request` (:class:`web.Request`) parameter
        - Must be asynchronous (defined using `async def`)
        - Should return some form of :class:`web.Response`
    """
    def decorator(func: Callable):
        if not isinstance(predicate, str) and not asyncio.iscoroutinefunction(predicate):
            raise TypeError("predicate must be a coroutine function")
        if not isinstance(fail_handler, str) and not asyncio.iscoroutinefunction(fail_handler):
            raise TypeError("fail_handler must be a coroutine function")
        require_self = bool(inspect.signature(func).parameters.get("self"))

        async def _check_wrapper__(*args, **kwargs):
            nonlocal predicate, fail_handler
            _self = kwargs.get("_bot_or_cog_self__")
            if _self:
                del kwargs["_bot_or_cog_self__"]
            if isinstance(predicate, str):
                predicate = getattr(_self, predicate)
            _pred = await predicate(*args, **kwargs)
            if not _pred:
                if isinstance(fail_handler, str):
                    fail_handler = getattr(_self, fail_handler)
                return await fail_handler(*args, **kwargs)
            if require_self:
                return await func(_self, *args, **kwargs)
            elif func.__name__ == "_check_wrapper__":
                return await func(*args, _bot_or_cog_self__=_self, **kwargs)
            return await func(*args, **kwargs)
        return _check_wrapper__
    return decorator
