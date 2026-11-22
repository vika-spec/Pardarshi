# Pardarshi web app (Next.js) for Azure Container Apps
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# The API address is baked into the /api proxy at build time
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_REPO_URL=https://github.com/vika-spec/Pardarshi
ENV NEXT_PUBLIC_REPO_URL=$NEXT_PUBLIC_REPO_URL
RUN npm run build && npm prune --omit=dev

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL
COPY --from=build /app/package.json /app/next.config.ts ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
