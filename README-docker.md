# StudBud - Docker Deployment

## Docker Quick Start

### Using Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/studbud.git
   cd studbud
   ```

2. **Set environment variables** (optional):
   ```bash
   # Create .env file
   echo "SECRET_KEY=your-super-secret-key-here" > .env
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Open http://localhost:3000 in your browser
   - Default admin credentials: `admin` / `dojo`

5. **Create admin user** (if needed):
   ```bash
   docker-compose exec studbud python -c "
   from models import db, User
   from extensions import db
   u = User(username='admin', role='admin', is_admin=True)
   u.set_password('dojo')
   db.session.add(u)
   db.session.commit()
   print('Admin user created')
   "
   ```

### Using Docker Run

```bash
# Build the image
docker build -t studbud .

# Run the container
docker run -d \
  --name studbud-app \
  -p 3000:3000 \
  -v studbud_data:/app/data \
  -v studbud_uploads:/app/static/uploads \
  -e SECRET_KEY=your-secret-key \
  studbud
```

## Data Persistence

The Docker setup includes two volumes for data persistence:

- **`studbud_data`**: SQLite database storage (`/app/data`)
- **`studbud_uploads`**: User-uploaded images (`/app/static/uploads`)

## Environment Variables

- **`SECRET_KEY`**: Flask secret key for session security
- **`DATA_DIR`**: Database directory (default: `/app/data` in container)
- **`FLASK_ENV`**: Flask environment (default: `production`)

## Management Commands

```bash
# View logs
docker-compose logs -f studbud

# Restart application
docker-compose restart studbud

# Stop application
docker-compose down

# Update application
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Backup database
docker-compose exec studbud cp /app/data/studbud.db /app/studbud-backup.db
docker cp studbud-app:/app/studbud-backup.db ./studbud-backup.db

# Restore database
docker cp ./studbud-backup.db studbud-app:/app/data/studbud.db
docker-compose restart studbud
```

## Health Check

The application includes a health endpoint at `/health` for monitoring:

```bash
curl http://localhost:3000/health
# Response: {"status": "healthy", "service": "StudBud"}
```

## Troubleshooting

### Container won't start
- Check logs: `docker-compose logs studbud`
- Verify port 3000 is available: `sudo lsof -i :3000`

### Database issues
- Reset volumes: `docker-compose down -v && docker-compose up -d`
- Check database permissions in container

### Image upload issues
- Verify uploads volume mount: `docker-compose exec studbud ls -la /app/static/uploads`
- Check container permissions

## Production Considerations

1. **Use proper secrets**: Set strong `SECRET_KEY` via environment variables
2. **Reverse proxy**: Use nginx or traefik for SSL termination
3. **Backups**: Regularly backup the database volume
4. **Updates**: Use tagged versions instead of `latest` for production
5. **Monitoring**: Monitor health endpoint and container logs

## Security Notes

- The application runs as non-root user (`studbud`) inside the container
- Database and uploads are stored in Docker volumes
- Default admin credentials should be changed after first login
- Use HTTPS in production environments