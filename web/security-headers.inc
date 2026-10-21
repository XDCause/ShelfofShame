# Safety headers, included by nginx.conf in the server and in each location that sets headers of
# its own (nginx drops the outer add_header lines in a location that has any).
#   nosniff                  a file is only ever treated as the type it says (a "photo" can't run as a page)
#   frame-ancestors / X-Frame-Options   other sites can't show the app inside a frame (click-jacking)
#   Referrer-Policy          links to other sites don't send them the app's addresses
#   Content-Security-Policy  only the app's own scripts run, and it only talks to its own API.
#                            Photos may also come from https: sites (Tamiya, HLJ, YouTube thumbnails),
#                            data: and blob: (photos being shrunk). Inline styles are needed by React
#                            and the journal editor. Fonts: our own copies (public/fonts); the
#                            drawing canvas lists esm.sh as a backup after them, and Chrome reports
#                            a blocked backup as an error even when it never needs it, so fonts
#                            may come from https://esm.sh too (only used if our copy is missing).
#   Permissions-Policy       (health check, 2026-10-21) the device features a page may use: passkeys yes;
#                            camera, microphone, location, payments and USB no (photos come through the file
#                            picker, which this doesn't touch). A feature the app starts using goes here first.
#   No HSTS on purpose: see nginx.conf (a home certificate).
add_header X-Content-Type-Options "nosniff" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=(), publickey-credentials-get=(self), publickey-credentials-create=(self)" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "same-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data: https://esm.sh; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'" always;
