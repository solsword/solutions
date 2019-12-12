# Create app secret key:
secret: Makefile
	head -c 16 /dev/urandom | hexdump -e '"%x"' > $@

# Create self-signed certificate for SSL:
.PHONY: cert
cert: Makefile
	openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

cert.pem: cert
key.pem: cert
