from typing import Dict, Set, Type, Union
import functools
import os
import keyword
import re
import inspect


# ========================================================================= #
# configurable                                                              #
# ========================================================================= #


class Configurable(object):
    # namespace pattern
    # https://docs.python.org/3/reference/lexical_analysis.html
    _NAME_PATTERN = re.compile('^([a-zA-Z0-9_]+|[*])([.][a-zA-Z0-9_]+)*$')

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
        return Configurable.get_fullname(self.func)

    @functools.cached_property
    def shortname(self) -> str:
        return Configurable.get_shortname(self.func)

    @functools.cached_property
    def configurable_param_names(self) -> Set[str]:
        params = inspect.signature(self.func).parameters
        return {k for k, p in params.items() if (p.default is not p.empty)}

    def make_wrapped_func(self, ns_config, global_config):
        assert self.is_dirty, 'Cannot make function if not dirty'
        self._is_dirty = False

        # get kwargs
        kwargs = {}
        for k in self.configurable_param_names:
            if k in ns_config:
                kwargs[k] = ns_config[k]
            elif k in global_config:
                kwargs[k] = global_config[k]

        # reinstantiate if _Instanced
        for k, v in kwargs.items():
            if isinstance(v, _Instanced):
                kwargs[k] = v()

        # make new function with default values
        return functools.partial(self.func, **kwargs)

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    def __str__(self):
        return self.fullname

    @staticmethod
    def get_fullname(func) -> str:
        """
        This name is not validated and could be wrong!
        Returns the import path to a function
        """
        # path to the module that the function is in without extension
        module_path = os.path.splitext(inspect.getmodule(func).__file__)[0]
        # strip the working directory from the path
        working_dir = os.getcwd().rstrip('/') + '/'
        assert module_path.startswith(working_dir)
        module_path = module_path[len(working_dir):]
        # replace slashes with dots and combine
        fullname = f'{module_path.replace("/", ".")}.{Configurable.get_shortname(func)}'
        return Configurable.validate_name(fullname)

    @staticmethod
    def get_shortname(func) -> str:
        shortname = func.__qualname__
        shortname = shortname.replace('.<locals>', '')  # handle nested functions
        return Configurable.validate_name(shortname)

    @staticmethod
    def can_configure(obj):
        return inspect.isfunction(obj) or inspect.isclass(obj)

    @staticmethod
    def validate_name(name) -> str:
        # CHECK PATTERN
        if not Configurable._NAME_PATTERN.match(name):
            raise ValueError(f'Invalid namespace and name: {repr(name)}')
        if any(keyword.iskeyword(n) for n in name.split('.')):
            raise ValueError(f'Namespace contains a python identifier')
        return name


# ========================================================================= #
# config                                                                    #
# ========================================================================= #


class Config(object):

    GLOBAL_NAMESPACE = '*'
    INSTANCED_CHAR = '@'

    def __init__(self, strict=False):
        self._CONFIGURABLES:     Dict[str, Configurable]      = {}  # namespace -> configurable
        self._NAMESPACE_PARAMS:  Dict[str, Set[str]]          = {}  # namespace -> param_names
        self._NAMESPACE_CONFIGS: Dict[str, Dict[str, object]] = {}  # namespace -> param_names -> values
        # if namespaces must not conflict
        self._strict: bool = strict

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Getters                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def has_namespace(self, namespace) -> bool:
        return (namespace in self._NAMESPACE_PARAMS) or (namespace == Config.GLOBAL_NAMESPACE)

    def has_namespace_param(self, namespace, param_name):
        return self.has_namespace(namespace) and (param_name in self._NAMESPACE_PARAMS[namespace])

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
            if self.has_namespace(configurable.namespace):
                raise KeyError(f'strict mode enabled, namespaces must be unique: {namespace}')
        self._NAMESPACE_PARAMS.setdefault(configurable.namespace, set()).update(configurable.configurable_param_names)

        # return the new configurable
        return configurable

    def _mark_all_dirty(self):
        # mark everything as dirty
        # TODO: detect changes?
        for path, configurable in self._CONFIGURABLES.items():
            configurable._is_dirty = True

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
                    ns_config = self._NAMESPACE_CONFIGS.get(configurable.namespace, {})
                    global_config = self._NAMESPACE_CONFIGS.get(Config.GLOBAL_NAMESPACE, {})
                    wrapped_func = configurable.make_wrapped_func(ns_config, global_config)
                    # TODO: log to debug logger
                    # print(f'[debug]: remade {configurable}')
                return wrapped_func(*args, **kwargs)
            return caller

        # support call without arguments
        if Configurable.can_configure(namespace):
            namespace_str = None  # compute default
            return decorate(namespace)
        else:
            namespace_str = namespace
            return decorate

    def reset(self):
        self.set({})

    def set(self, flat_config):
        """Set the current configuration"""
        self._NAMESPACE_CONFIGS = self._flat_config_to_namespace_configs(flat_config)
        self._mark_all_dirty()

    def update(self, flat_config):
        """Update the current configuration, overriding values"""
        ns_config = self._flat_config_to_namespace_configs(flat_config)
        # merge all namespace configs
        for namespace, ns_conf in ns_config.items():
            self._NAMESPACE_CONFIGS.setdefault(namespace, {}).update(ns_conf)
        self._mark_all_dirty()

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # conversion                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _convert_if_instanced_for_load(self, path, func):
        """used when loading/setting the config"""
        if path.startswith(Config.INSTANCED_CHAR):
            if isinstance(func, str):
                # get registered function if this is a string
                if not func in self._CONFIGURABLES:
                    raise KeyError(f'Not a valid path to a registered function: {func}')
                func = self._CONFIGURABLES[func].func
            else:
                # check that the function is configurable
                if not Configurable.can_configure(func):
                    raise ValueError(f'value marked as Instanced is not configurable "{path}": {func}')
                # check that the function is registered
                fullname = Configurable.get_fullname(func)
                if fullname not in self._CONFIGURABLES:
                    raise KeyError(f'function set as Instanced has not been registered as a configurable "{path}": {fullname}')
            return path[1:], _Instanced(func)
        return path, func

    def _convert_if_instanced_for_save(self, path, value):
        """used when saving"""
        if isinstance(value, _Instanced):
            # no checks needed because we validated on updating/setting the config
            path = Config.INSTANCED_CHAR + path
            value = Configurable.get_fullname(value.func)
        return path, value

    def _flat_config_to_namespace_configs(self, flat_config: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        namespace_configs = {}
        # Validate names and store defaults
        for path, value in flat_config.items():
            # check is instanced variable first, and convert if it is.
            path, value = self._convert_if_instanced_for_load(path, value)
            # then validate
            Configurable.validate_name(path)
            namespace, name = path.rsplit('.', 1)
            # check everything exists
            if self._strict:
                if not self.has_namespace(namespace):
                    raise KeyError(f'namespace does not exist: {namespace}')
                if not self.has_namespace_param(namespace, name):
                    raise KeyError(f'name "{name}" on namespace "{namespace}" does not exist')
            # store new defaults
            namespace_configs.setdefault(namespace, {})[name] = value
        return namespace_configs

    def _namespace_configs_to_flat_config(self, ns_config: Dict[str, Dict[str, object]]):
        flat_config = {}
        for namespace in sorted(ns_config):
            conf = ns_config[namespace]
            for name in sorted(conf):
                path, value = f'{namespace}.{name}', conf[name]
                # try convert to an instanced variable if necessary
                path, value = self._convert_if_instanced_for_save(path, value)
                flat_config[path] = value
        return flat_config

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # IO                                                                    #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def save_config(self, file_path):
        import toml
        with open(file_path, 'w') as file:
            data = self._namespace_configs_to_flat_config(self._NAMESPACE_CONFIGS)
            toml.dump(data, file)
            print(f'[SAVED CONFIG]: {os.path.abspath(file_path)}')

    def load_config(self, file_path):
        import toml
        with open(file_path, 'r') as file:
            data = toml.load(file)
            self.set(data)
            print(f'[LOADED CONFIG]: {os.path.abspath(file_path)}')

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Utility                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def print(self):
        """
        Print out all the configurable parameters along with their namespace as well as their
        values if the values are specified in the current configuration.
        The printed string in most simple cases should be valid python code to allow easy copy pasting!
        - it does not reduce overridden values down to global variables, but comments if that is the reason.

        TODO: clean up this method... it is super messy and horrible...
        """
        grn, red, ylw, gry, ppl, blu, rst = '\033[92m', '\033[91m', '\033[93m', '\033[90m', '\033[95m', '\033[94m', '\033[0m'
        clr_ns, clr_param, clr_val, clr_glb = ppl, blu, ylw, red
        # print namespaces
        configured_global = self._NAMESPACE_CONFIGS.get(Config.GLOBAL_NAMESPACE, {})
        # opening brace
        sb = [f'{gry}{{{rst}\n']
        # append strings
        for namespace in sorted(self._NAMESPACE_PARAMS):
            configured = self._NAMESPACE_CONFIGS.get(namespace, {})
            for param in sorted(self._NAMESPACE_PARAMS[namespace]):
                is_l, is_g = (param in configured), (param in configured_global)
                # space or comment out
                sb.append('  ' if (is_l or is_g) else f'{gry}# ')
                # dictionary key as the namespace.param
                val = (configured[param] if is_l else configured_global[param]) if (is_l or is_g) else None
                sb.append(f'{gry}"{grn}{_Instanced.get_prefix(val)}{rst}{clr_ns}{namespace}{gry}.{clr_param}{param}{gry}"{rst}: ')
                # dictionary func
                if is_l or is_g:
                    if is_l:
                        sb.append(f'{clr_val}{repr(val)}')
                    elif is_g:
                        sb.append(f'{clr_glb}{repr(val)}')
                # comma
                sb.append(f'{gry},{rst}')
                # comment if has a global func assigned to it
                if is_g:
                    val = configured_global[param]
                    sb.append(f'  {gry}# "{_Instanced.get_prefix(val)}{Config.GLOBAL_NAMESPACE}.{param}{gry}": {repr(val)},{rst}')
                # new line
                sb.append('\n')
        # closing brace
        sb.append(f'{gry}}}{rst}')
        # generate string!
        print(''.join(sb))

class _Instanced(object):
    def __init__(self, func):
        if not callable(func):
            print(f'[\033[91m{func}\033[0m]')
            func = globals()[func]
        self.func = func

    def __call__(self):
        return self.func()

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return Configurable.get_fullname(self.func)

    @staticmethod
    def get_prefix(value):
        if isinstance(value, _Instanced):
            return Config.INSTANCED_CHAR
        return ''

# ========================================================================= #
# END                                                                       #
# ========================================================================= #
