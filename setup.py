import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='tonic-config',
    url='https://github.com/nmichlo/tonic-config',

    # automatic versions
    version_config={
        "version_format": "{tag}.dev{sha}",
        "starting_version": "0.1.0"
    },
    setup_requires=['better-setuptools-git-version'],

    # explicit version
    # version='0.0.1',

    # Author Information
    author='Nathan Michlo',
    author_email='NathanJMichlo@gmail.com',

    # Project Information
    description='Lightweight configuration framework for Python, combining the most notable aspects of Gin and Sacred.',
    long_description=long_description,
    long_description_content_type='text/markdown',

    # Project Dependencies
    python_requires='>=3.6',
    packages=setuptools.find_packages(),

    #
    # https://pypi.org/classifiers/
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Utilities'
    ],

)