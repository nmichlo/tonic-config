# UPLOADING TO PYPI... I really should remember this by now:
# $ python setup.py sdist
# $ twine upload dist/*

import setuptools

# read description
with open('README.md', 'r') as fh:
    LONG_DESCRIPTION = fh.read()
with open('requirements.txt') as fh:
    REQUIREMENTS = fh.readlines()
with open('requirements_test.txt') as fh:
    REQUIREMENTS_TEST = fh.readlines()

# setup
setuptools.setup(
    name='tonic-config',
    url='https://github.com/nmichlo/tonic-config',

    # explicit version
    version='0.1.5',

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
    install_requires=REQUIREMENTS,
    tests_require=REQUIREMENTS_TEST,

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
