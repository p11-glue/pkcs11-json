$(srcdir)/subprojects/pkcs11-json/generated/pkcs11.json: $(PKCS11_JSON_INPUT)
	$(AM_V_GEN)$(CASTXML) > /dev/null && $(PYTHON) $(srcdir)/subprojects/pkcs11-json/gen.py $< --outfile $@ --castxml-program $(CASTXML)

pkcs11.json: $(srcdir)/subprojects/pkcs11-json/generated/pkcs11.json
	$(AM_V_GEN)cp $< $@

EXTRA_DIST += \
	$(srcdir)/subprojects/pkcs11-json/meson.build \
	$(srcdir)/subprojects/pkcs11-json/gen.py \
	$(srcdir)/subprojects/pkcs11-json/README.md \
	$(srcdir)/subprojects/pkcs11-json/generated/pkcs11.json \
	$(NULL)
