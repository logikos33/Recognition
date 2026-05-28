#!/bin/sh
PORT=${PORT:-80}
sed "s/\${PORT}/$PORT/g" /etc/nginx/nginx.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g "daemon off;"
