ARG BUILD_FROM
ARG UPSTREAM_IMAGE=usethefork/ryobi_gdo_2_mqtt:latest

FROM ${UPSTREAM_IMAGE} as ryobi_gdo_2_mqtt

FROM ${BUILD_FROM}
WORKDIR /app

# Bring along Python, uv, dependencies, and the application from the upstream image
COPY --from=ryobi_gdo_2_mqtt /usr/local /usr/local
COPY --from=ryobi_gdo_2_mqtt /app /app

COPY run.sh /run.sh
RUN chmod a+x /run.sh
ENV PATH="/usr/local/bin:${PATH}"

CMD [ "/run.sh" ]
