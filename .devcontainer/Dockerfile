FROM mcr.microsoft.com/devcontainers/universal:2

# Remove the expired Yarn GPG key and repository to prevent apt-get update failures
RUN rm -f /etc/apt/sources.list.d/yarn.list 2>/dev/null || true && \
    rm -f /usr/share/keyrings/yarn-keyring.gpg 2>/dev/null || true && \
    rm -f /etc/apt/trusted.gpg.d/yarn.gpg 2>/dev/null || true && \
    apt-key del 23E7166788B63E1E 2>/dev/null || true && \
    apt-get update || true
