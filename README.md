# pkcs11-json

pkcs11-json is a project to provide a JSON based, machine readable
representation of PKCS #11 interface for further code generation.

## Usage

```console
$ sudo dnf install castxml
$ git clone --depth=1 https://github.com/p11-glue/p11-kit.git
$ castxml --castxml-output=1 p11-kit/common/pkcs11.h
$ python gen.py pkcs11.xml > pkcs11.json
```

## License

BSD-3-Clause
