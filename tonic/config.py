import keyword
import os
import re
import inspect


# ========================================================================= #
# config                                                                    #
# ========================================================================= #


class Namespace:
    """
    Nested namespace classes with member values can be converted to a configuration
    where the name of the classes in the hierarchy correspond to the namespace names
    """
    def __init__(self):
        raise Exception('Namespace should not be instantiated')


class Config(object):

    def __init__(self, strict=True):
        # current configuration
        self._CONFIG = {}       # namespace to dict of parameters to values
        self._USED = {}         # namespace to set of parameter names
        self._DEFAULTS = {}     # full_namespace to dict of parameters to values
        self._FULL_TO_NAME = {} # full_namespace to namespace
        # namespace pattern
        # https://docs.python.org/3/reference/lexical_analysis.html
        self._pattern = re.compile('^([a-zA-Z0-9][a-zA-Z0-9_]*)([.][a-zA-Z0-9][a-zA-Z0-9_]*)*$')
        # if namespaces must not conflict
        self._strict = strict

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Helper                                                                #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _get_namespace(self, func, full=True):
        """
        This name is not validated and could be wrong!
        Returns the import path to a function
        """
        if full:
            # path to the module that the function is in without extension
            module_path = os.path.splitext(inspect.getmodule(func).__file__)[0]
            # strip the working directory from the path
            working_dir = os.getcwd().rstrip('/') + '/'
            assert module_path.startswith(working_dir)
            module_path = module_path[len(working_dir):]
            # replace slashes with dots and combine
            return f'{module_path.replace("/", ".")}.{self._get_name(func)}'
        else:
            return self._get_name(func)

    def _get_name(self, func):
        name = func.__qualname__
        name = name.replace('.<locals>', '')  # handle nested functions
        return name

    def _register_function(self, func, namespace):
        """Register a function to the config engine"""
        namespace_full = self._get_namespace(func, full=True)
        self._validate_name(namespace_full)
        # get function parameters with default values
        params = inspect.signature(func).parameters
        params_default = {k: p for k, p in params.items() if (p.default is not p.empty)}
        # add parameter names to correct namespace
        if self._strict:
            if namespace in self._USED:
                raise KeyError(f'namespace already used: {namespace}')
        self._USED.setdefault(namespace, set()).update(params_default.keys())
        # store defaults under full_namespace, must not conflict!
        assert namespace_full not in self._DEFAULTS, 'This should never happen!'
        self._FULL_TO_NAME[namespace_full] = namespace
        self._DEFAULTS[namespace_full] = {k: p.default for k, p in params_default.items()}

    def _validate_name(self, name):
        if not self._pattern.match(name):
            raise ValueError(f'Invalid namespace and name: {repr(name)}')
        if any(keyword.iskeyword(n) for n in name.split('.')):
            raise ValueError(f'Namespace contains a python identifier')

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Decorators                                                            #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def __call__(self, func_or_namespace, full=False):
        # check if the decorator was called with arguments
        called_with_args = not (inspect.isfunction(func_or_namespace) or inspect.isclass(func_or_namespace))
        # get the namespace
        namespace = func_or_namespace if called_with_args else self._get_namespace(func_or_namespace, full=full)
        self._validate_name(namespace)
        # decorate!
        def wrap(func):
            self._register_function(func, namespace)
            # make a new function to call those parameters with config values if they exist
            def call_with_config(*args, **kwargs):
                return func(*args, **{
                    **self._CONFIG.get(namespace, {}),  # config
                    **kwargs                            # override config with passed kwargs
                })
            # return new function
            return call_with_config
        # act as decorator if not called with arguments, otherwise return the decorator
        return wrap if called_with_args else wrap(func_or_namespace)

    def set(self, config):
        """Set the current configuration"""
        config = self.as_config(config)
        # Validate names
        self._CONFIG = {}
        for k, v in config.items():
            self._validate_name(k)
            namespace, name = k.rsplit('.', 1)
            self._CONFIG.setdefault(namespace, {})[name] = v
        # Check names exist
        for namespace, n_config in self._CONFIG.items():
            if namespace not in self._USED:
                raise KeyError(f'namespace does not exist: {namespace}'
                               f' Valid namespaces are: [{", ".join(self._USED.keys())}]')
            for name in n_config.keys():
                if name not in self._USED[namespace]:
                    raise KeyError(f'name "{name}" on namespace "{namespace}" does not exist'
                                   f' Valid names are: [{", ".join(self._USED[namespace])}]')

    def update(self, config):
        """Update the current configuration, overriding values"""
        self.set({
            **self._USED,
            **self.as_config(config),
        })

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Config classes                                                        #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def _is_namespace_class(self, cls):
        return inspect.isclass(cls) and issubclass(cls, Namespace)

    def as_config(self, config):
        """Make sure the config is a dictionary, attempt conversion if it is not"""
        if isinstance(config, dict):
            return config
        else:
            assert self._is_namespace_class(config)
        dict_config, path = {}, config.__name__
        for name in (name for name in dir(config) if not name.startswith('_')):
            value = getattr(config, name)
            if self._is_namespace_class(value):
                for n, v in self.as_config(value).items():
                    dict_config[f'{path}.{n}'] = v
            else:
                dict_config[f'{path}.{name}'] = value
        return dict_config

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # IO                                                                    #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def save_config(self, file_path):
        import toml
        with open(file_path, 'w') as file:
            toml.dump(self._CONFIG, file)

    def load_config(self, file_path):
        import toml
        with open(file_path, 'r') as file:
            config = toml.load(file)
            self.set(config)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #
    # Utility                                                               #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - #

    def print(self, full=False):
        # colours
        grn, red, ylw, gry, rst = '\033[92m', '\033[91m', '\033[93m', '\033[90m', '\033[0m'
        print_values = []
        # generate values
        for full_namespace in sorted(self._FULL_TO_NAME, key=self._FULL_TO_NAME.__getitem__):
            full_namespace_defaults = self._DEFAULTS[full_namespace]
            namespace = self._FULL_TO_NAME[full_namespace]
            namespace_config = self._CONFIG.get(namespace, {})
            for name in sorted(full_namespace_defaults):
                if name in sorted(namespace_config):
                    print_values.append((f'{gry}{full_namespace if full else namespace}{rst}.{red}{name}{rst}', f'{red}{namespace_config[name]}{rst} ({ylw}{full_namespace_defaults[name]}{rst})'))
                else:
                    print_values.append((f'{gry}{full_namespace if full else namespace}{rst}.{grn}{name}{rst}', f'{ylw}{full_namespace_defaults[name]}{rst}'))
        # print all values
        max_len = max(len(x[0]) for x in print_values)
        for name_str, val_str in print_values:
            print(f'{name_str:{max_len}s} = {val_str}')

# ========================================================================= #
# END                                                                       #
# ========================================================================= #
