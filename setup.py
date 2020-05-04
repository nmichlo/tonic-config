import subprocess
import setuptools

# get git info
GIT_COMMITS_SINCE_LAST_TAG = subprocess.getoutput(f'git rev-list "$(git tag --sort=version:refname --merged | tail -n1)..HEAD" --count')

# read description
with open('README.md', 'r') as fh:
    LONG_DESCRIPTION = fh.read()

# setup
setuptools.setup(
    name='tonic-config',
    url='https://github.com/nmichlo/tonic-config',

    # automatic version [better-setuptools-git-version]
    version_config={
        'version_format': '{tag}.dev' + GIT_COMMITS_SINCE_LAST_TAG + '.{sha}',
        'starting_version': '0.1.0'
    },

    # explicit version
    # version='0.0.1',

    # Author Information
    author='Nathan Michlo',
    author_email='NathanJMichlo@gmail.com',

    # Project Information
    description='Lightweight configuration framework for Python, combining the most notable aspects of Gin and Sacred.',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',

    # Project Dependencies
    python_requires='>=3.6',
    packages=setuptools.find_packages('tonic'),

    # requirements
    install_requires=['toml'],
    tests_require=['pytest'],
    setup_requires=['better-setuptools-git-version'],

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
