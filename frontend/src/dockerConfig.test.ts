import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const repoRoot = path.resolve('..');

describe('Docker frontend integration', () => {
  it('uses same-origin API proxying and SPA fallback in Nginx', () => {
    const dockerfile = fs.readFileSync(path.join(repoRoot, 'frontend', 'Dockerfile'), 'utf8');
    const nginx = fs.readFileSync(path.join(repoRoot, 'frontend', 'nginx.conf'), 'utf8');
    const compose = fs.readFileSync(path.join(repoRoot, 'docker-compose.yml'), 'utf8');

    expect(dockerfile).toContain('ARG VITE_API_BASE_URL=/api');
    expect(dockerfile).toContain('COPY nginx.conf /etc/nginx/conf.d/default.conf');
    expect(nginx).toContain('try_files $uri $uri/ /index.html;');
    expect(nginx).toContain('proxy_pass http://backend:8100;');
    expect(compose).toContain('context: ./frontend');
    expect(compose).toContain('VITE_API_BASE_URL: /api');
  });

  it('runs migrations before the Docker backend starts Uvicorn', () => {
    const dockerfile = fs.readFileSync(path.join(repoRoot, 'backend', 'Dockerfile'), 'utf8');

    expect(dockerfile).toContain('python -m app.migrations.runner up');
    expect(dockerfile).toContain('exec python -m uvicorn app.main:app');
  });
});
