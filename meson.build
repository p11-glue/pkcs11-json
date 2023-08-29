project('pkcs11-json')

castxml = find_program('castxml', required: false)
if castxml.found()
  pkcs11_json_gen = generator(
    find_program('gen.py'),
    output: '@BASENAME@.json',
    arguments: [
      '@INPUT@', '--outfile', '@OUTPUT@',
      '--castxml-program', castxml.path(),
    ],
  )
else
  pkcs11_json_gen = generator(
    find_program('cp'),
    output: '@BASENAME@.json',
    arguments: [
      meson.project_source_root() / 'generated' / 'pkcs11.json', '@OUTPUT@',
    ],
  )
endif
