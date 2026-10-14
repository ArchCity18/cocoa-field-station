FROM php:8.3-apache

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev python3 \
    && docker-php-ext-install pdo_pgsql \
    && rm -rf /var/lib/apt/lists/* \
    && a2enmod headers

WORKDIR /var/www/html/cocoa-security
COPY api.php ./api.php
COPY deploy/php-entrypoint.py /usr/local/bin/cocoa-php-entrypoint.py
RUN chmod +x /usr/local/bin/cocoa-php-entrypoint.py
EXPOSE 80
ENTRYPOINT ["python3", "/usr/local/bin/cocoa-php-entrypoint.py"]