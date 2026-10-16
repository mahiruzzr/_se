FROM rust:1-slim-bookworm AS builder

WORKDIR /app

COPY rust-api/Cargo.toml rust-api/Cargo.lock ./
RUN mkdir -p src && printf 'fn main() {}\n' > src/main.rs && cargo build --release && rm -rf src

COPY rust-api/src ./src
RUN touch src/main.rs && cargo build --release

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/rust-api /usr/local/bin/rust-api

EXPOSE 8080
CMD ["rust-api"]
