# Docker Build Optimization Guide

## Optimizations Applied

The Dockerfile has been optimized for faster `pip install` steps:

1. **Layer Caching**: Dependency files are copied first, then installed, then source code is copied
2. **Pip Cache Mounting**: Uses BuildKit cache mounts to reuse downloaded packages
3. **Requirements.txt**: Installs from `requirements/base.txt` (faster than pyproject.toml)
4. **Pip Upgrade**: Upgrades pip, setuptools, and wheel first for better performance
5. **Prefer Binary**: Uses `--prefer-binary` flag to prefer pre-built wheels

## Building with Optimizations

### Enable BuildKit (Required for cache mounting)

**Option 1: Environment Variable (Recommended)**
```bash
export DOCKER_BUILDKIT=1
docker compose build
```

**Option 2: Build Command Flag**
```bash
DOCKER_BUILDKIT=1 docker compose build
```

**Option 3: Docker Desktop**
BuildKit is enabled by default in Docker Desktop. No action needed.

### Build Commands

**Standard build:**
```bash
docker compose build
```

**Build with cache:**
```bash
DOCKER_BUILDKIT=1 docker compose build --build-arg BUILDKIT_INLINE_CACHE=1
```

**Build without cache (clean build):**
```bash
docker compose build --no-cache
```

## Expected Performance Improvements

- **First build**: Similar time (all packages need to be downloaded)
- **Subsequent builds** (dependencies unchanged): **50-90% faster** due to layer caching
- **Subsequent builds** (source code changed only): **80-95% faster** - dependencies layer is cached
- **With pip cache mount**: **30-60% faster** on clean builds

## Troubleshooting

### BuildKit Not Available

If you see errors about `--mount` flag, BuildKit is not enabled. Either:
1. Enable BuildKit: `export DOCKER_BUILDKIT=1`
2. Or remove the `--mount` line from Dockerfile (line 24) and use:
   ```dockerfile
   RUN pip install --no-cache-dir --prefer-binary -r requirements/base.txt
   ```

### Cache Not Working

- Ensure BuildKit is enabled
- Check that dependency files (`requirements/base.txt`, `pyproject.toml`) haven't changed
- Verify Docker has enough disk space for cache

## Additional Tips

1. **Use .dockerignore**: Already configured to exclude unnecessary files
2. **Multi-stage builds**: Consider for even smaller final images (not yet implemented)
3. **Pin versions**: Exact version pins in requirements.txt improve cache hit rates

