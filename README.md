# pkcs11-json

pkcs11-json is a project to provide a JSON based, machine readable
representation of PKCS #11 interface for further code generation.

## Generating the JSON file

```console
$ sudo dnf install castxml
$ git clone --depth=1 https://github.com/p11-glue/p11-kit.git
$ castxml --castxml-output=1 p11-kit/common/pkcs11.h
$ python gen.py pkcs11.xml > pkcs11.json
```

## Integrating with build systems

### Meson

In the top-level `meson.build`, set `pkcs11_json_input` to a path to
"pkcs11.h", and include the `pkcs11-json` subdirectory.

```meson
python = import('python').find_installation()
pkcs11_json_input = meson.project_source_root() / 'common' / 'pkcs11.h'
subdir('pkcs11-json')
```

`pkcs11_json` will point to the generated JSON file.

### Autotools

In `configure.ac`, check for the `castxml` program:

```autoconf
AM_MISSING_PROG([PYTHON], [python])
AM_MISSING_PROG([CASTXML], [castxml])
```

In `Makefile.am`, set `PKCS11_JSON_INPUT` to a path to "pkcs11.h", and include `pkcs11-json/Makefile.am`:

```makefile
PKCS11_JSON_INPUT = $(srcdir)/common/pkcs11.h

include pkcs11-json/Makefile.am
```

## License

BSD-3-Clause
