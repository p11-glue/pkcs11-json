castxml = find_program('castxml')

if castxml.found()
  pkcs11_xml = custom_target(
    'pkcs11.xml',
    output: 'pkcs11.xml',
    input: pkcs11_json_input,
    command: [
      castxml,
      '--castxml-output=1', '@INPUT@', '-o', '@OUTPUT@',
    ],
  )

  pkcs11_json = custom_target(
    'pkcs11.json',
    output: 'pkcs11.json',
    input: pkcs11_xml,
    command: [
      find_program('gen.py'),
      '@INPUT@', '--outfile', '@OUTPUT@',
    ],
  )
else
  pkcs11_json = custom_target(
    'pkcs11.json',
    output: 'pkcs11.json',
    input: meson.source_root() / 'pkcs11-json' / 'generated' / 'pkcs11.json',
    command: [
      'cp', '@INPUT@', '@OUTPUT@',
    ],
  )
endif
