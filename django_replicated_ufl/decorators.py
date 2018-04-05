# coding: utf-8
'''
Decorators for using specific routing state for particular requests.
Used in cases when automatic switching based on request method doesn't
work.

Usage:

    from django_replicated.decorators import use_master, use_slave

    @use_master
    def my_view(request, ...):
        # master database used for all db operations during
        # execution of the view (if not explicitly overriden).

    @use_slave
    def my_view(request, ...):
        # same with slave connection
'''
from __future__ import unicode_literals

from functools import wraps

from django.utils.decorators import decorator_from_middleware_with_args

from .middleware import ReplicationMiddleware
from .utils import routers

try:
    from django.utils.decorators import ContextDecorator
except ImportError:
    class ContextDecorator(object):
        """
        A base class that enables a context manager to also be used as a decorator.
        """

        def __call__(self, func):
            @wraps(func)
            def inner(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)

            return inner

use_state = decorator_from_middleware_with_args(ReplicationMiddleware)
use_master = use_state(forced_state='master')
use_slave = use_state(forced_state='slave')


class use_state_simple(ContextDecorator):
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        routers.use_state(self.state)

    def __exit__(self, exc_type, exc_val, exc_tb):
        routers.revert()


use_master_simple = use_state_simple('master')
use_slave_simple = use_state_simple('slave')


def make_db_class_based_decorator(*args1, **kwargs1):
    def _make_decorator(view_func):
        middleware = ReplicationMiddleware(*args1, **kwargs1)

        def _decorator(_, request, *args, **kwargs):
            result = middleware.process_request(request)
            if result is not None:
                return result

            result = middleware.process_view(request, view_func, args, kwargs)
            if result is not None:
                return result

            try:
                response = view_func(_, request, *args, **kwargs)
            except Exception as e:
                if hasattr(middleware, 'process_exception'):
                    result = middleware.process_exception(request, e)
                    if result is not None:
                        return result
                raise

            if hasattr(response, 'render') and callable(response.render):
                if hasattr(middleware, 'process_template_response'):
                    response = middleware.process_template_response(request, response)
                # Defer running of process_response until after the template
                # has been rendered:
                if hasattr(middleware, 'process_response'):
                    callback = lambda response: middleware.process_response(request, response)
                    response.add_post_render_callback(callback)
            else:
                if hasattr(middleware, 'process_response'):
                    return middleware.process_response(request, response)

            return response

        return _decorator

    return _make_decorator

use_slave_class_based = make_db_class_based_decorator(forced_state='slave')
use_master_class_based = make_db_class_based_decorator(forced_state='master')