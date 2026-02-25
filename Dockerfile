# Stage 1: Build the Next.js application
FROM node:16-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Copy source code
COPY . .

# Build the Next.js application
RUN yarn build

# Stage 2: Production runtime
FROM node:16-alpine AS production

# Set working directory
WORKDIR /app

# Set NODE_ENV to production
ENV NODE_ENV=production

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Copy package files
COPY package.json yarn.lock ./

# Copy built application and node_modules from builder stage
# This includes all dependencies needed for babel-node to work
COPY --from=builder --chown=nodejs:nodejs /app/web/.next ./web/.next
COPY --from=builder --chown=nodejs:nodejs /app/server ./server
COPY --from=builder --chown=nodejs:nodejs /app/shared ./shared
COPY --from=builder --chown=nodejs:nodejs /app/web ./web
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nodejs:nodejs /app/babel.config.js ./
COPY --from=builder --chown=nodejs:nodejs /app/jest.config.js ./

# Switch to non-root user
USER nodejs

# Expose the application port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/favicon.ico', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start the production server using yarn start (babel-node)
CMD ["yarn", "start"]