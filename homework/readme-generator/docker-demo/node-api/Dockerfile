FROM node:22-alpine

WORKDIR /app

COPY node-api/package.json node-api/package-lock.json ./
RUN npm ci --omit=dev

COPY node-api/server.js ./

ENV NODE_ENV=production
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
