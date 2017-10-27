from setuptools import setup

setup(
    name = "eventlet_pyqt",
    version = "0.1.2",
    py_modules = ["eventlet_pyqt"],
    zip_safe = True,

    # metadata for upload to PyPI
    author = "Qize Huang",
    author_email = "hgoldfish@gmail.com",
    description = "Integrate eventlet with Qt's eventloop.",
    license = "LGPL",
    keywords = "qt eventlet pyqt gevent",
    url = "https://github.com/hgoldfish/eventlet-pyqt",

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python',
    ],
)
