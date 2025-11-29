FROM debian:bookworm-slim AS base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    nodejs \
    npm \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    texlive-latex-extra \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force
COPY compile.js ./

# create non-root user
RUN useradd -m -u 1001 latexuser \
  && mkdir -p /tmp/platex-jobs \
  && chown -R latexuser:latexuser /tmp/platex-jobs /usr/src/app

USER latexuser
EXPOSE 7000
CMD ["node", "compile.js"]
