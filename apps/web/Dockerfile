FROM oven/bun:1.1

WORKDIR /app

COPY package.json /app/package.json
RUN bun install

COPY . /app
RUN bun run prepare

EXPOSE 5173

CMD ["bun", "run", "dev"]
