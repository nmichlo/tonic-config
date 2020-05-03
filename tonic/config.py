import functools
from typing import Dict, List, Set, Type, Union
import os
import keyword
import re
import inspect


# ========================================================================= #
# namespace                                                                 #
# ========================================================================= #


class Namespace:
    """
    Nested namespace classes with member values can be converted to a configuration
    where the name of the classes in the hierarchy correspond to the namespace names
    """
    def __init__(self):
        raise Exception('Namespace should not be instantiated')

    @staticmethod
    def is_namespace(cls):
        return inspect.isclass(cls) and issubclass(cls, Namespace)


# ========================================================================= #
# configurable                                                              #
# ========================================================================= #


class Configurable(object):
    # namespace pattern
    # https://docs.python.org/3/reference/lexical_analysis.html
    # _NAME_PATTERN = re.compile('^([a-zA-Z0-9][a-zA-Z0-9_]*)([.][a-zA-Z0-9][a-zA-Z0-9_]*)*$')
    _NAME_PATTERN = re.compile('^([a-zA-Z0-9_]+)([.][a-zA-Z0-9_]+)*$')

    def __init__(self, func, namespace=None):
        if not callable(func):
            raise ValueError(f'Configurable must be callable: {func}')
        # the function which should be configured
        self.func: callable = func
        # the namespace which shares parameter values
        self.namespace: str = self.shortname if (namespace is None) else self.validate_name(namespace)
        # if the function needs to be remade
        self._dirty = True

    @functools.cached_property
    def fullname(self) -> str:
        """
        This name is not validated and could be wrong!
        Returns the import path to a function
        """
        # path to the module that the function is in without extension
        module_path = os.path.splitext(inspect.getmodule(self.func).__file__)[0]
        # strip the working directory from the path
        working_dir = os.getcwd().rstrip('/') + '/'
        assert module_path.startswith(working_dir)
        module_path = module_path[len(working_dir):]
        # replace slashes with dots and combine
        fullname = f'{module_path.replace("/", ".")}.{self.shortname}'
        return self.validate_name(fullname)

    @functools.cached_property
    def shortname(self) -> str:
        shortname = self.func.__qualname__
        shortname = shortname.replace('.<locals>', '')  # handle nested functions
        return self.validate_name(shortname)

    @functools.cached_property
    def configurable_param_names(self) -> Set[str]:
        params = inspect.signature(self.func).parameters
        return {k for k, p in params.items() if (p.default is not p.empty)}

    @staticmethod
    def can_configure(obj):
        return inspect.isfunction(obj) or inspect.isclass(obj)

    @staticmethod
    def validate_name(name) -> str:
        if not Configurable._NAME_PATTERN.match(name):
            raise ValueError(f'Invalid namespace and name: {repr(name)}')
        if any(keyword.iskeyword(n) for n in name.split('.')):
            raise ValueError(f'Namespace contains a python identifier')
        return name

    def make_wrapped_func(self, ns_config):
        assert self.is_dirty, 'Cannot make function if not dirty'
        self._is_dirty = False
        return functools.partial(self.func, **{
            k: v
            for k, v in ns_config.items()
            if k in self.configurable_param_names
        })

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    def __str__(self):
        return self.fullname


# ========================================================================= #
# config                                                                    #
# ========================================================================= #


class Config(object):

    def __init__(self, strict=True, is_namespaced=True):
        self._CONFIGURABLES:      Dict[str, Configurable]       = {}
        self._NAMESPACE_PARAMS:   Dict[str, Set[str]]           = {}
        self._NAMESPACE_CONFIGS:  Dict[str, Dict[str, object]]  = {}
        # if namespaces must not conflict
        self._strict: bool = strict

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Helper                                                                #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _register_function(self, func, namespace=None) -> Configurable:
        """Register a function to the config engine"""
        configurable = Configurable(func, namespace)

        # check that we have not already registered the configurable
        if configurable.fullname in self._CONFIGURABLES:
            raise KeyError(f'configurable already registered: {configurable.fullname}')
        self._CONFIGURABLES[configurable.fullname] = configurable

        # check that we have not registered the namespace
        if self._strict:
            if configurable.namespace is self._NAMESPACE_PARAMS:
                raise KeyError(f'strict mode enabled, namespaces must be unique: {namespace}')
        self._NAMESPACE_PARAMS.setdefault(configurable.namespace, set()).update(configurable.configurable_param_names)

        # return the new configurable
        return configurable

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Decorators                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def __call__(self, namespace):
        def decorate(func):
            configurable = self._register_function(func, namespace_str)
            wrapped_func = None

            @functools.wraps(func)  # copy name, docs, etc.
            def caller(*args, **kwargs):
                nonlocal wrapped_func
                if configurable.is_dirty:
                    ns_config = self._NAMESPACE_CONFIGS[configurable.namespace] if configurable.namespace in self._NAMESPACE_CONFIGS else {}
                    wrapped_func = configurable.make_wrapped_func(ns_config)
                    print(f'[debug]: remade {configurable}')
                return wrapped_func(*args, **kwargs)
            return caller

        # support call without arguments
        if Configurable.can_configure(namespace):
            namespace_str = None  # compute default
            return decorate(namespace)
        else:
            namespace_str = namespace
            return decorate

    def has_namespace(self, namespace) -> bool:
        return namespace not in self._NAMESPACE_PARAMS

    def has_namespace_param(self, namespace, param_name):
        return self.has_namespace(namespace) and (param_name in self._NAMESPACE_PARAMS[namespace])

    def _raw_config_to_namespace_configs(self, raw_config: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        raw_config = self._as_raw_config(raw_config)
        namespace_configs = {}
        # Validate names and store defaults
        for param_name, value in raw_config.items():
            Configurable.validate_name(param_name)
            namespace, name = param_name.rsplit('.', 1)
            # check everything exists
            if self.has_namespace(namespace):
                raise KeyError(f'namespace does not exist: {namespace}')
            if self.has_namespace_param(namespace, param_name):
                raise KeyError(f'name "{name}" on namespace "{namespace}" does not exist')
            # store new defaults
            namespace_configs.setdefault(namespace, {})[name] = value
        return namespace_configs

    def _namespace_configs_to_raw_config(self, ns_config: Dict[str, Dict[str, object]]):
        return {
            f'{namespace}.{name}': value
            for namespace, names in ns_config.items()
            for name, value in names.items()
        }

    def _mark_all_dirty(self):
        # mark everything as dirty
        # TODO: detect changes?
        for path, configurable in self._CONFIGURABLES.items():
            configurable._is_dirty = True

    def reset(self):
        self.set({})

    def set(self, raw_config):
        """Set the current configuration"""
        self._NAMESPACE_CONFIGS = self._raw_config_to_namespace_configs(raw_config)
        self._mark_all_dirty()

    def update(self, raw_config):
        """Update the current configuration, overriding values"""
        ns_config = self._raw_config_to_namespace_configs(self._as_raw_config(raw_config))
        # merge all namespace configs
        for namespace, ns_config in ns_config.items():
            self._NAMESPACE_CONFIGS.setdefault(namespace, {}).update(ns_config)
        self._mark_all_dirty()

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Config classes                                                        #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _as_raw_config(self, config: Union[Dict, Type[Namespace]]) -> Dict[str, object]:
        """Make sure the config is a dictionary, attempt conversion if it is not"""
        if isinstance(config, dict):
            return config
        else:
            assert Namespace.is_namespace(config)
        # convert if the config is actually a namespace class
        raw_config: Dict[str, object] = {}
        path = config.__name__
        for name in (name for name in dir(config) if not name.startswith('_')):
            value = getattr(config, name)
            if Namespace.is_namespace(value):
                for n, v in self._as_raw_config(value).items():
                    raw_config[f'{path}.{n}'] = v
            else:
                raw_config[f'{path}.{name}'] = value
        # return the raw config
        return raw_config

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # IO                                                                    #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def save_config(self, file_path, namespaced=True):
        import toml
        with open(file_path, 'w') as file:
            data = self._NAMESPACE_CONFIGS
            data = data if namespaced else self._namespace_configs_to_raw_config(data)
            toml.dump(data, file)
            print(f'[SAVED CONFIG]: {os.path.abspath(file_path)}')

    def load_config(self, file_path, namespaced=True):
        import toml
        with open(file_path, 'r') as file:
            data = toml.load(file)
            data = self._namespace_configs_to_raw_config(data) if namespaced else data
            self.set(data)
            print(f'[LOADED CONFIG]: {os.path.abspath(file_path)}')

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Utility                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def print(self):
        # colours
        grn, red, ylw, gry, ppl, blu, rst = '\033[92m', '\033[91m', '\033[93m', '\033[90m', '\033[95m', '\033[94m', '\033[0m'
        # print namespaces
        for namespace in sorted(self._NAMESPACE_PARAMS):
            configured = self._NAMESPACE_CONFIGS.get(namespace, {})
            print(f'[{gry}"{ppl}{namespace}{gry}"{rst}]')
            for param in sorted(self._NAMESPACE_PARAMS[namespace]):
                if param in configured:
                    print(f'{ylw}{param}{rst} = {blu}{repr(configured[param])}{rst}')
                else:
                    print(f'{red}{param}{rst}')
            print()


# ========================================================================= #
# END                                                                       #
# ========================================================================= #

config = Config()

@config
def test(a, b, c=2, d=3):
    print(a, b, c, d)

@config('test.test')
def test2(a, b, c=2, d=3):
    print(a, b, c, d)

config.set({
    # global parameters
    # '*._seed': 100,

    # Per Instance Parameters
    # '*._random': Instanced(np.random),

    'test.c': 55,
    'test.test.d': 77,
    'test.test.c': 100,
})

test(0, 1, c=77)
test(0, 1)
test2(0, 1)
test2(0, 1)

config.save_config('test_conf.toml')
config.reset()

test(0, 1)
test(0, 1)
test2(0, 1)
test2(0, 1)

config.load_config('test_conf.toml')

test(0, 1)
test(0, 1)
test2(0, 1)
test2(0, 1)

config.print()
