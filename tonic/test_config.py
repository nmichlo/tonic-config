import tonic



# ========================================================================= #
# test_config                                                               #
# ========================================================================= #

def do_test(get_wrapped, config, target):
    # reset tonic config
    tonic_config = tonic.Config()
    # @tonic.config
    wrapped = get_wrapped(tonic_config)
    # set configuration
    tonic_config.set(config)
    # now test
    assert wrapped() == target


def train(optimizer='adam', lr=0.001):
    return optimizer, lr


def test_defaults():
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    wrapped = tonic.config(train)
    # set configuration
    tonic.config.set({
        'train.optimizer': 'sgd',
        'train.lr': 0.005,
    })
    # now test
    assert wrapped() == ('sgd', 0.005)

def test_namespaced():
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    wrapped = tonic.config('train_namespace.inner_namespace')(train)
    # set configuration
    tonic.config.set({
        'train_namespace.inner_namespace.optimizer': 'sgd',
        'train_namespace.inner_namespace.lr': 0.005,
    })
    # now test
    assert wrapped() == ('sgd', 0.005)

def test_local_nested():
    # NESTED FUNCTION
    def train_nested(optimizer='adam', lr=0.001):
        return optimizer, lr
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    wrapped = tonic.config(train_nested)
    # set configuration
    tonic.config.set({
        'test_local_nested.train_nested.optimizer': 'sgd',
        'test_local_nested.train_nested.lr': 0.005,
    })
    # now test
    assert wrapped() == ('sgd', 0.005)

def test_class():
    # NESTED FUNCTION
    class Trainer(object):
        def __init__(self, optimizer='adam', lr=0.001):
            self.optimizer = optimizer
            self.lr = lr
        def get(self):
            return self.optimizer, self.lr
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    WrappedCls = tonic.config(Trainer)
    # set configuration
    tonic.config.set({
        'test_class.Trainer.optimizer': 'sgd',
        'test_class.Trainer.lr': 0.005,
    })
    # now test
    assert WrappedCls().get()                          == ('sgd', 0.005)

    # TODO: these dont work
    # assert WrappedCls('radam').get()                 == ('radam', 0.005)
    # assert WrappedCls('radam', 0.1).get()            == ('radam', 0.1)
    # assert WrappedCls('radam', lr=0.1).get()         == ('radam', 0.1)

    assert WrappedCls(lr=0.1).get()                    == ('sgd', 0.1)
    assert WrappedCls(optimizer='radam', lr=0.1).get() == ('radam', 0.1)
    assert WrappedCls(optimizer='radam').get()         == ('radam', 0.005)


# ========================================================================= #
# END                                                                       #
# ========================================================================= #
