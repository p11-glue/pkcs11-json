$(srcdir)/pkcs11-json/generated/pkcs11.xml: $(PKCS11_JSON_INPUT)
	$(AM_V_GEN)$(CASTXML) --castxml-output=1 $< -o $@

$(srcdir)/pkcs11-json/generated/pkcs11.json: $(srcdir)/pkcs11-json/generated/pkcs11.xml
	$(AM_V_GEN)$(PYTHON) $(srcdir)/pkcs11-json/gen.py $< --outfile $@

pkcs11.json: $(srcdir)/pkcs11-json/generated/pkcs11.json
	$(AM_V_GEN)cp $< $@

EXTRA_DIST += \
	$(srcdir)/pkcs11-json/meson.build \
	$(srcdir)/pkcs11-json/gen.py \
	$(srcdir)/pkcs11-json/README.md \
	$(srcdir)/pkcs11-json/generated/pkcs11.json \
	$(srcdir)/pkcs11-json/generated/pkcs11.xml \
	$(NULL)
