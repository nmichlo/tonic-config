import types
from typing import Dict, Set, Union
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


# Base type of a configurable
ConfigurableFunc = Union[types.FunctionType, types.MethodType, type]


class Configurable(object):
    """
    _Configurable manages the configurable
    parameters of a registered function or class.

    Used internally by Config.
    """
    # namespace pattern
    # https://docs.python.org/3/reference/lexical_analysis.html
    _KEY_PATTERN  = re.compile(r'^@?(([*][.])|(\w+[.])+)?(\w+)$')

    def __init__(self, func, nid=None, cid=None):
        if not Configurable.can_configure(func):
            raise ValueError(f'Configurable must be callable: {func}')
        # the function which should be configured
        self._func: ConfigurableFunc = func
        # the configurable identifier - we use the nid instead of the cid by default
        self.cid: str = Configurable.nid_from_func(func) if (cid is None) else self.validate_id(cid)
        # the namespace which shares parameter values
        self.nid: str = Configurable.nid_from_func(func) if (nid is None) else self.validate_id(nid)
        # if the function needs to be remade
        self._is_dirty = True
        # temp configurations, only set when dirty
        self._last_ns_config = None
        self._last_global_config = None

    def __str__(self):
        return f'{self.cid} ({self.nid})'

    @cached_property
    def configurable_param_names(self) -> Set[str]:
        """
        Get all configurable parameters of the function.
        ie. return all the parameters with default values.
        """
        params = inspect.signature(self._func).parameters
        return {k for k, p in params.items() if (p.default is not p.empty)}

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
                v = ns_config[k]
            elif k in global_config:
                v = global_config[k]
            else:
                continue
            kwargs[k] = Instanced.try_instantiate(v)

        # make new function
        return functools.partial(self._func, **kwargs)

    def reconfigure(self, ns_config, global_config):
        self._last_ns_config = ns_config
        self._last_global_config = global_config
        self._is_dirty = True

    @cached_property
    def decorated_func(self):
        defaults_func = None

        # copy name, docs, etc.
        @functools.wraps(self._func)
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

    @staticmethod
    def can_configure(obj) -> bool:
        """
        If the specified object is configurable.
        ie. a function or a class
        """
        return isinstance(obj, (types.FunctionType, types.MethodType, type))

    @staticmethod
    def cid_from_func(func) -> str:
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
        fullname = f'{module_path.replace("/", ".")}.{Configurable.nid_from_func(func)}'
        return Configurable.validate_id(fullname)

    @staticmethod
    def nid_from_func(func) -> str:
        """
        The processed __qualname__ of the function or class.
        """
        nid = func.__qualname__
        nid = nid.replace('.<locals>', '')  # handle nested functions
        return Configurable.validate_id(nid)

    @staticmethod
    def validate_id(name) -> str:
        """
        ids can only contain valid python identifiers separated by dots.

        :param name: name to validate according to _Configurable._NAME_PATTERN
        :return: return the input name exactly as is.
        """
        # CHECK PATTERN
        if not Configurable._KEY_PATTERN.match(name):
            raise ValueError(f'Invalid namespace and name: {repr(name)}')
        if any(keyword.iskeyword(n) for n in name.split('.')):
            raise ValueError(f'Namespace and name contains a python identifier')
        return name


# ========================================================================= #
# namespace                                                                 #
# ========================================================================= #


class Namespace(object):
    def __init__(self, nid):
        self.nid: str = nid
        self._param_names: Set[str] = set()
        self._configurables: Dict[str, Configurable] = {}

    def __contains__(self, param):
        return param in self._param_names

    def __iter__(self):
        return self._param_names.__iter__()

    def get_configurable(self, cid: str) -> Configurable:
        return self._configurables[cid]

    def register_configurable(self, configurable: Configurable):
        if self.has_configurable(configurable):
            raise KeyError('Configurable already registered on namespace')
        # register configurable with namespace
        self._configurables[configurable.cid] = configurable
        self._param_names.update(configurable.configurable_param_names)

    def has_configurable(self, configurable: Configurable):
        return configurable.cid in self._configurables


# ========================================================================= #
# config                                                                    #
# ========================================================================= #


class Config(object):

    GLOBAL_NAMESPACE = '*'
    INSTANCED_CHAR = '@'

    def __init__(self):
        self._configurables: Dict[str, Configurable] = {}
        self._namespaces: Dict[str, Namespace] = {}
        self._namespace_configs: Dict[str, Dict[str, object]] = {}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # getters                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def has_namespace(self, namespace) -> bool:
        """
        Check if a namespace exists, but also handles the case of the GLOBAL_NAMESPACE
        which is usually not a valid registration.
        """
        return namespace in self._namespaces

    def has_namespace_param(self, namespace, param_name) -> bool:
        """
        If a namespace has the specified parameter.
        returns false if the namespace itself does not exist instead of raising a KeyError
        """
        return self.has_namespace(namespace) and (param_name in self._namespaces[namespace])

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # configurables                                                         #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _reconfigure(self, configurable: Configurable):
        configurable.reconfigure(
            self._namespace_configs.get(configurable.nid, {}),
            self._namespace_configs.get(Config.GLOBAL_NAMESPACE, {})
        )

    def _reconfigure_all(self) -> None:
        """
        Mark all configurables as dirty.
        Used internally by set() and update().
        TODO: This is not the most efficient implementation, changes are not detected.
        """
        global_config = self._namespace_configs.get(Config.GLOBAL_NAMESPACE, {})
        for configurable in self._configurables.values():
            ns_config = self._namespace_configs.get(configurable.nid, {})
            configurable.reconfigure(ns_config, global_config)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Decorators                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def __call__(self, namespace, cid=None):
        """
        Decorator that registers a configurable.
        Shorthand for Config.configurable(...)
        """
        return self.configure(namespace, cid)

    def configure(self, namespace, cid=None):
        """
        Decorator that registers a configurable.

        A function also needs to be registered as configurable
        if it is to be used as a tonic instanced parameter.

        :param namespace: namespace is the namespace under which parameters will be grouped for configuration
        :param cid: the name that the function will be registered under, preferably leave this blank.
        :return: decorated configurable function
        """
        def register(func):
            cfgable = Configurable(func, namespace_str, cid)
            # [1] register configurable to namespace
            if cfgable.nid not in self._namespaces:
                self._namespaces[cfgable.nid] = Namespace(cfgable.nid)
            self._namespaces[cfgable.nid].register_configurable(cfgable)

            # [2] register configurable to configurables
            if cfgable.cid in self._configurables:
                raise KeyError(f'configurable already registered: {cfgable.cid} try specifying cid="<unique_path>"')
            self._configurables[cfgable.cid] = cfgable

            # [3] configure for the first time
            self._reconfigure(cfgable)

            # return the new configurable
            return cfgable.decorated_func

        # support call without arguments
        if Configurable.can_configure(namespace):
            namespace_str = None  # compute default
            return register(namespace)
        else:
            namespace_str = namespace
            return register

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
        self._namespace_configs = self._flat_config_to_namespace_configs(flat_config)
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
            self._namespace_configs.setdefault(namespace, {}).update(ns_conf)
        self._reconfigure_all()

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # conversion                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _flat_config_to_namespace_configs(self, flat_config: Dict[str, object]) -> Dict[str, Dict[str, object]]:
        """
        Convert a flat configuration to a dictionary of namespaces with parameters.
        Used as the internal data structure which is easier to work with.
        """
        namespace_configs = {}
        # Validate names and store defaults
        for key, value in flat_config.items():
            # check is instanced variable first, and convert if it is.
            key, value = Instanced.convert_for_load(self._configurables, key, value)
            # then validate
            Configurable.validate_id(key)
            namespace, param = key.rsplit('.', 1)
            # store new defaults
            namespace_configs.setdefault(namespace, {})[param] = value
        return namespace_configs

    @staticmethod
    def _namespace_configs_to_flat_config(ns_config: Dict[str, Dict[str, object]]):
        """
        Convert a dictionary of namespaces to parameters, back to a flat configuration.
        Used for saving the internal state in a way the user is familiar with.
        """
        flat_config = {}
        for namespace in sorted(ns_config):
            conf = ns_config[namespace]
            for name in sorted(conf):
                key, value = f'{namespace}.{name}', conf[name]
                # try convert to an instanced variable if necessary
                key, value = Instanced.convert_for_save(key, value)
                flat_config[key] = value
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
            data = self._namespace_configs_to_flat_config(self._namespace_configs)
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
        configured_global = self._namespace_configs.get(Config.GLOBAL_NAMESPACE, {})
        # opening brace
        sb = [f'{gry}{{{rst}\n']
        # append strings
        for namespace in sorted(self._namespaces):
            configured = self._namespace_configs.get(namespace, {})
            for param in sorted(self._namespaces[namespace]):
                is_l, is_g = (param in configured), (param in configured_global)
                # space or comment out
                sb.append('  ' if (is_l or is_g) else f'{gry}# ')
                # dictionary key as the namespace.param
                val = configured.get(param, configured_global.get(param, None))
                sb.append(f'{gry}"{grn}{Instanced.get_prefix(val)}{rst}{clr_ns}{namespace}{gry}.{clr_param}{param}{gry}"{rst}: ')
                # dictionary func
                if is_l or is_g:
                    sb.append(f'{clr_val if is_l else clr_glb}{repr(val)}')
                # comma
                sb.append(f'{gry},{rst}')
                # comment if has a global func assigned to it
                if is_g:
                    val = configured_global[param]
                    sb.append(f'  {gry}# "{Instanced.get_prefix(val)}{Config.GLOBAL_NAMESPACE}.{param}{gry}": {repr(val)},{rst}')
                # new line
                sb.append('\n')
        # closing brace
        sb.append(f'{gry}}}{rst}')
        # generate string!
        print(''.join(sb))


# ========================================================================= #
# Instanced Value                                                           #
# ========================================================================= #

# TODO: this can be replaced with a dictionary of instanced values
class Instanced(object):
    """
    See Config.set() for a description of Instanced values.
    Handled internally, and not exposed to the user.

    prefix path with @, ie.
    @<namespace>.<name> marks the corresponding value as instanced.
    if marked as instanced, the <value> must be a registered configurable
    """

    def __init__(self, configurable: Configurable):
        self.configurable = configurable

    @staticmethod
    def try_instantiate(value):
        if isinstance(value, Instanced):
            return value.configurable.decorated_func()
        return value

    @staticmethod
    def convert_for_save(key, value) -> (str, object):
        """
        Convert a path & Instanced(registered_func) to a @path & fullname
        Used when saving
        """
        # no checks needed because we validated on updating/setting the config
        if isinstance(value, Instanced):
            return f'{Config.INSTANCED_CHAR}{key}', value.configurable.nid
        return key, value

    @staticmethod
    def convert_for_load(configurables: Dict[str, Configurable], key, value) -> (str, object):
        """
        Convert a @path & value to a path & Instance(registered_func) if possible.
        Used when loading/setting the config
        """
        if key.startswith(Config.INSTANCED_CHAR):
            if isinstance(value, str):
                cid = value
                if cid not in configurables:
                    raise KeyError(f'Could not find a registered configurable matching the cid marked as instanced "{key}": "{cid}"')
            elif Configurable.can_configure(value):
                cid = Configurable.nid_from_func(value)
                if cid not in configurables:
                    raise KeyError(f'function marked as Instanced has not been registered as a configurable "{key}": "{cid}"')
            else:
                raise ValueError(f'value marked as Instanced is not configurable "{key}": "{value}"')
            return key[1:], Instanced(configurables[cid])  # self._configurables[cid]
        return key, value

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

    @staticmethod
    def get_prefix(value):
        if isinstance(value, Instanced):
            return Config.INSTANCED_CHAR
        return ''

# ========================================================================= #
# END                                                                       #
# ========================================================================= #
