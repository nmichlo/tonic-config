from typing import Dict, Set
import functools
import os
import keyword
import re
import inspect

# functools has cached_property but only for python 3.8+
from cached_property import cached_property


# ========================================================================= #
# configurable                                                              #
# ========================================================================= #


class _Configurable(object):
    """
    _Configurable manages the configurable
    parameters of a registered function or class.

    Used internally by Config.
    """

    # namespace pattern
    # https://docs.python.org/3/reference/lexical_analysis.html
    _NAME_PATTERN = re.compile('^([a-zA-Z0-9_]+|[*])([.][a-zA-Z0-9_]+)*$')

    def __init__(self, func, namespace=None):
        if not callable(func):
            raise ValueError(f'_Configurable must be callable: {func}')
        # the function which should be configured
        self._func: callable = func
        # the namespace which shares parameter values
        self.namespace: str = self.shortname if (namespace is None) else self.validate_name(namespace)
        # if the function needs to be remade
        self._is_dirty = True
        # temp configurations, only set when dirty
        self._last_ns_config = None
        self._last_global_config = None

    @cached_property
    def fullname(self) -> str:
        """See _Configurable.get_fullname(...)"""
        return _Configurable.get_fullname(self._func)

    @cached_property
    def shortname(self) -> str:
        """See _Configurable.get_fullname(...)"""
        return _Configurable.get_shortname(self._func)

    @cached_property
    def configurable_param_names(self) -> Set[str]:
        """
        Get all configurable parameters of the function.
        ie. return all the parameters with default values.
        """
        params = inspect.signature(self._func).parameters
        return {k for k, p in params.items() if (p.default is not p.empty)}

    def __call__(self, *args, **kwargs):
        return self.decorated_func(*args, **kwargs)

    def _make_defaults_func(self, ns_config, global_config):
        """
        Create a wrapped function for the configurable based on the default
        values given from the namespace (takes priority) and global namespace (lower priority)

        Also instantiates any values that are marked as instanced to be used as the new default.

        :return: the wrapped/configured function
        """
        if (self._last_ns_config is None) or (self._last_global_config is None):
            raise RuntimeError('Reconfigure not called before trying to call configurable.')
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
        # make new function
        return functools.partial(self._func, **kwargs)

    def reconfigure(self, ns_config, global_config):
        self._last_ns_config = ns_config
        self._last_global_config = global_config
        self._is_dirty = True

    @cached_property
    def decorated_func(self):
        defaults_func = None # we dont expose this
        @functools.wraps(self._func)  # copy name, docs, etc.
        def remake_if_dirty(*args, **kwargs):
            nonlocal defaults_func
            if self._is_dirty:
                defaults_func = self._make_defaults_func(self._last_ns_config, self._last_global_config)
                # mark as non-dirty
                self._is_dirty = False
                self._last_ns_config = None
                self._last_global_config = None
            # call our configured function!
            return defaults_func(*args, **kwargs)
        return remake_if_dirty

    def __str__(self):
        return self.fullname

    @staticmethod
    def get_fullname(func) -> str:
        """
        This name is not validated and could be wrong!
        Returns the import path to a function
        """
        # register to the module that the function is in without extension
        module_path = os.path.splitext(inspect.getmodule(func).__file__)[0]
        # strip the working directory from the register
        working_dir = os.getcwd().rstrip('/') + '/'
        assert module_path.startswith(working_dir)
        module_path = module_path[len(working_dir):]
        # replace slashes with dots and combine
        fullname = f'{module_path.replace("/", ".")}.{_Configurable.get_shortname(func)}'
        return _Configurable.validate_name(fullname)

    @staticmethod
    def get_shortname(func) -> str:
        """
        The processed __qualname__ of the function or class.
        """
        shortname = func.__qualname__
        shortname = shortname.replace('.<locals>', '')  # handle nested functions
        return _Configurable.validate_name(shortname)

    @staticmethod
    def can_configure(obj) -> bool:
        """
        If the specified object is configurable.
        ie. a function or a class
        """
        return inspect.isfunction(obj) or inspect.isclass(obj)

    @staticmethod
    def validate_name(name) -> str:
        """
        names can only contain valid python identifiers separated by dots.
        Think python imports.

        :param name: name to validate according to _Configurable._NAME_PATTERN
        :return: return the input name exactly as is.
        """
        # CHECK PATTERN
        if not _Configurable._NAME_PATTERN.match(name):
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
        self._CONFIGURABLES:     Dict[str, _Configurable]      = {}  # namespace -> configurable
        self._NAMESPACE_PARAMS:  Dict[str, Set[str]]          = {}  # namespace -> param_names
        self._NAMESPACE_CONFIGS: Dict[str, Dict[str, object]] = {}  # namespace -> param_names -> values
        # if namespaces must not conflict
        self._strict: bool = strict

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Getters                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def has_namespace(self, namespace) -> bool:
        """
        Check if a namespace exists, but also handles the case of the GLOBAL_NAMESPACE
        which is usually not a valid registration.
        """
        return (namespace in self._NAMESPACE_PARAMS) or (namespace == Config.GLOBAL_NAMESPACE)

    def has_namespace_param(self, namespace, param_name) -> bool:
        """
        If a namespace has the specified parameter.
        returns false if the namespace itself does not exist instead of raising a KeyError
        """
        return self.has_namespace(namespace) and (param_name in self._NAMESPACE_PARAMS[namespace])

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Helper                                                                #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _register_function(self, func, namespace=None, register=None) -> _Configurable:
        """
        Used internally by the Config.configurable to create a new
        configurable from a function and perform checks.

        :param func: The configurable function
        :param namespace: The namespace to bind parameters to.
        :param register: The name to register the function under, preferably do not use this.
        :return: new configurable corresponding to the function
        """

        """Register a function to the config engine"""
        configurable = _Configurable(func, namespace)

        # check that we have not already registered the configurable
        register = configurable.shortname if (register is None) else _Configurable.validate_name(register)
        if register in self._CONFIGURABLES:
            raise KeyError(f'configurable already registered: {register} try specifying register="<unique_path>"')
        self._CONFIGURABLES[register] = configurable

        # check that we have not registered the namespace
        if self._strict:
            if self.has_namespace(configurable.namespace):
                raise KeyError(f'strict mode enabled, namespaces must be unique: {namespace}')
        self._NAMESPACE_PARAMS.setdefault(configurable.namespace, set()).update(configurable.configurable_param_names)

        # reconfigure configurable
        # TODO: this might be called to early and update the configurable with values
        #  that are not expected due to later additions?
        configurable.reconfigure(
            self._NAMESPACE_CONFIGS.get(configurable.namespace, {}),
            self._NAMESPACE_CONFIGS.get(Config.GLOBAL_NAMESPACE, {})
        )

        # return the new configurable
        return configurable

    def _reconfigure_all(self) -> None:
        """
        Mark all configurables as dirty.
        Used internally by set() and update().
        TODO: This is not the most efficient implementation, changes are not detected.
        """
        global_config = self._NAMESPACE_CONFIGS.get(Config.GLOBAL_NAMESPACE, {})
        for path, configurable in self._CONFIGURABLES.items():
            ns_config = self._NAMESPACE_CONFIGS.get(configurable.namespace, {})
            configurable.reconfigure(ns_config, global_config)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Decorators                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def __call__(self, namespace):
        """
        Decorator that registers a configurable.
        Shorthand for Config.configurable(...)
        """
        return self.configure(namespace)

    def configure(self, namespace, register=None):
        """
        Decorator that registers a configurable.

        A function also needs to be registered as configurable
        if it is to be used as a tonic instanced parameter.

        :param namespace: namespace is the namespace under which parameters will be grouped for configuration
        :param register: register is the name that the function will be registered under, preferably leave this blank.
        :return: decorated configurable function
        """
        def decorate(func):
            configurable = self._register_function(func, namespace_str, register)
            return configurable.decorated_func

        # support call without arguments
        if _Configurable.can_configure(namespace):
            namespace_str = None  # compute default
            return decorate(namespace)
        else:
            namespace_str = namespace
            return decorate

    def reset(self) -> None:
        """
        Reset the configuration to defaults.
        """
        self.set({})

    def set(self, flat_config: Dict[str, object]) -> None:
        """
        Set the configuration using flat configuration schema, this also marks
        all registered configurables as dirty, meaning their functions and instanced
        parameters will be lazily regenerated.

        The configuration scheme for the dictionary is as follows:
           standard value: "<namespace>.<param>": <value>
           global value: "*.<param>": <value>
           instanced value: "@<namespace>.<param>": <registered configurable>

        Instanced values are instantiated PER function, and are reinstantiated
        every time a configurable is marked as dirty. IE. every time the config
        is set or updated.
        - eg. this is useful for passing around random instances for example.

        :param flat_config: a flat config
        """
        self._NAMESPACE_CONFIGS = self._flat_config_to_namespace_configs(flat_config)
        self._reconfigure_all()

    def update(self, flat_config: Dict[str, object]) -> None:
        """
        Functionally the same as set, but instead merges the configuration
        with the existing one, overwriting any values.

        see: set()
        """
        ns_config = self._flat_config_to_namespace_configs(flat_config)
        # merge all namespace configs
        for namespace, ns_conf in ns_config.items():
            self._NAMESPACE_CONFIGS.setdefault(namespace, {}).update(ns_conf)
        self._reconfigure_all()

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # conversion                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _convert_if_instanced_for_load(self, path, value) -> (str, object):
        """
        Convert a @path & value to a path & Instance(registered_func) if possible.
        Used when loading/setting the config
        """
        if path.startswith(Config.INSTANCED_CHAR):
            if isinstance(value, str):
                # get registered function if this is a string
                if value not in self._CONFIGURABLES:
                    raise KeyError(f'Not a valid register to a registered function: {value}')
                fullname = value
            else:
                # check that the function is configurable
                if not _Configurable.can_configure(value):
                    raise ValueError(f'value marked as Instanced is not configurable "{path}": {value}')
                # check that the function is registered
                fullname = _Configurable.get_shortname(value) # TODO: this corresponds to register_function
                if fullname not in self._CONFIGURABLES:
                    raise KeyError(f'function set as Instanced has not been registered as a configurable "{path}": {fullname}')
            return path[1:], _Instanced(self._CONFIGURABLES[fullname])
        return path, value

    def _convert_if_instanced_for_save(self, path, value) -> (str, object):
        """
        Convert a path & Instanced(registered_func) to a @path & fullname
        Used when saving
        """
        if isinstance(value, _Instanced):
            # no checks needed because we validated on updating/setting the config
            path = Config.INSTANCED_CHAR + path
            value = value.configurable.shortname # TODO: must be in _CONFIGURABLES
            assert value in self._CONFIGURABLES, 'This should never happen, please submit a bug report!'
        return path, value

    def _flat_config_to_namespace_configs(self, flat_config: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        """
        Convert a flat configuration to a dictionary of namespaces with parameters.
        Used as the internal data structure which is easier to work with.
        """
        namespace_configs = {}
        # Validate names and store defaults
        for path, value in flat_config.items():
            # check is instanced variable first, and convert if it is.
            path, value = self._convert_if_instanced_for_load(path, value)
            # then validate
            _Configurable.validate_name(path)
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
        """
        Convert a dictionary of namespaces to parameters, back to a flat configuration.
        Used for saving the internal state in a way the user is familiar with.
        """
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

    def save_config(self, file_path) -> None:
        """
        Save the current configuration to the specified TOML file.
        :param file_path:
        """
        import toml
        with open(file_path, 'w') as file:
            data = self._namespace_configs_to_flat_config(self._NAMESPACE_CONFIGS)
            toml.dump(data, file)
            print(f'[SAVED CONFIG]: {os.path.abspath(file_path)}')

    def load_config(self, file_path) -> None:
        """
        Read and set() the configuration from the specified TOML file.
        :param file_path:
        """
        import toml
        with open(file_path, 'r') as file:
            data = toml.load(file)
            self.set(data)
            print(f'[LOADED CONFIG]: {os.path.abspath(file_path)}')

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Utility                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def print(self) -> None:
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


# ========================================================================= #
# Instanced Value                                                           #
# ========================================================================= #


class _Instanced(object):
    """
    See Config.set() for a description of Instanced values.
    Handled internally, and not exposed to the user.

    prefix path with @, ie.
    @<namespace>.<name> marks the corresponding value as instanced.
    if marked as instanced, the <value> must be a registered configurable
    """

    def __init__(self, configurable):
        if not isinstance(configurable, _Configurable):
            raise RuntimeError('This should never happen! Please submit a bug report!')
        self.configurable = configurable

    def __call__(self):
        return self.configurable()

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return self.configurable.fullname

    @staticmethod
    def get_prefix(value):
        if isinstance(value, _Instanced):
            return Config.INSTANCED_CHAR
        return ''

# ========================================================================= #
# END                                                                       #
# ========================================================================= #
