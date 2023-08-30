# pkcs11-json

pkcs11-json is a project to provide a JSON based, machine readable
representation of PKCS #11 interface for further code generation.

## Generating the JSON file

```console
$ sudo dnf install castxml
$ git clone --depth=1 https://github.com/p11-glue/p11-kit.git
$ python gen.py p11-kit/common/pkcs11.h > pkcs11.json
```

## Integrating with build systems

### Meson

In the top-level `meson.build`, check for Python:

```meson
python = import('python').find_installation()
python_version = python.language_version()
python_version_req = '>=3.6'
if not python_version.version_compare(python_version_req)
  error('Requires Python @0@, @1@ found.'.format(python_version_req, python_version))
endif
```

Then import `pkcs11-json` as a subproject, generate JSON file through
the `pkcs11_json_gen` generator:

```meson
pkcs11_json_project = subproject('pkcs11-json')
pkcs11_json_gen = pkcs11_json_project.get_variable('pkcs11_json_gen')
pkcs11_json = pkcs11_json_gen.process('common/pkcs11.h')
```

### Autotools

In `configure.ac`, check for Python and the `castxml` program:

```autoconf
AM_PATH_PYTHON([3.6],, [:])
AM_MISSING_PROG([CASTXML], [castxml])
```

In `Makefile.am`, set `PKCS11_JSON_INPUT` to a path to "pkcs11.h", and include `pkcs11-json/Makefile.am`:

```makefile
PKCS11_JSON_INPUT = $(srcdir)/common/pkcs11.h

include pkcs11-json/Makefile.am
```

## License

BSD-3-Clause
