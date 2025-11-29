FROM node:20-bookworm-slim

WORKDIR /usr/src/app
COPY package.json ./
RUN npm install --omit=dev && npm cache clean --force
COPY server.js ./

ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]
