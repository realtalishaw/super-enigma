# Integrations Page

The Integrations page provides a modern, grid-based interface for browsing and searching through available integrations (toolkits) in the workflow automation engine.

## Features

### 🎯 **Pagination & Performance**
- **First 10 on load**: Shows first 10 integrations immediately for fast initial page load
- **Load more**: Additional integrations are loaded on-demand via "Load More" button
- **Search optimization**: Search results are paginated to maintain performance

### 🔍 **Search & Filtering**
- **Real-time search**: Search integrations by name or description with 300ms debouncing
- **Category tabs**: Filter integrations by category (All, Most used, Video conferencing, etc.)
- **Results counter**: Shows current view count vs total available integrations

### 🎨 **Modern UI Design**
- **Grid layout**: Responsive 4-column grid that adapts to screen size
- **Card design**: Clean integration cards with icons, names, descriptions, and status
- **Hover effects**: Subtle animations and hover states for better UX
- **Status indicators**: Shows "Connected" or "Connect" buttons for each integration

## API Endpoints

### Backend API (`/api/integrations`)
```http
GET /api/integrations?limit=10&offset=0&search=email
```

**Parameters:**
- `limit` (optional): Number of integrations to return (default: all)
- `offset` (optional): Starting position for pagination (default: 0)
- `search` (optional): Search term for filtering integrations

**Response:**
```json
{
  "items": [...],
  "total": 150,
  "limit": 10,
  "offset": 0,
  "hasMore": true
}
```

### Dedicated Search Endpoint (`/api/integrations/search`)
```http
GET /api/integrations/search?q=email&limit=20&offset=0
```

**Parameters:**
- `q` (required): Search query string
- `limit` (optional): Number of results to return (default: 20)
- `offset` (optional): Starting position for pagination (default: 0)

**Response:**
```json
{
  "items": [...],
  "query": "email",
  "total": 25,
  "limit": 20,
  "offset": 0
}
```

### Get Integration by Slug (`/api/integrations/{slug}`)
```http
GET /api/integrations/gmail
```

**Response:**
```json
{
  "id": "gmail-123",
  "slug": "gmail",
  "name": "Gmail",
  "description": "Send automated emails from your Gmail account",
  "logo": "/static/icons/gmail.svg",
  "category": "email",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Frontend Routes
- `/integrations` - Main integrations page
- `/partials/integrations` - HTMX partial for integration lists (legacy)

## Implementation Details

### Frontend Components
- **Page**: `app/templates/pages/integrations.html`
- **Route**: `app/ui_routes.py` → `integrations_page()`
- **Styling**: `app/static/css/main.css` (additional utilities)

### Backend Changes
- **API Route**: `api/routes/frontend/integrations.py`
- **Pagination**: Added `limit` and `offset` parameters
- **Count Query**: Separate query for total count calculation
- **Response Format**: Enhanced response with pagination metadata
- **Search Endpoint**: Dedicated `/search` endpoint with optimized search logic
- **Slug Endpoint**: Get individual integration details by slug

### Database Queries
```sql
-- Count query for total
SELECT COUNT(*) as total FROM toolkits t WHERE t.is_deprecated = FALSE

-- Main query with pagination
SELECT toolkit_id, slug, name, description, logo_url, category 
FROM toolkits t 
WHERE t.is_deprecated = FALSE 
ORDER BY t.name 
LIMIT :limit OFFSET :offset

-- Search query with ranking
SELECT toolkit_id, slug, name, description, logo_url, category
FROM toolkits t
WHERE t.is_deprecated = FALSE
AND (
    LOWER(t.name) LIKE LOWER(:search) 
    OR LOWER(t.description) LIKE LOWER(:search)
    OR LOWER(t.slug) LIKE LOWER(:search)
)
ORDER BY 
    CASE 
        WHEN LOWER(t.name) LIKE LOWER(:exact_search) THEN 1
        WHEN LOWER(t.name) LIKE LOWER(:search) THEN 2
        ELSE 3
    END,
    t.name
LIMIT :limit OFFSET :offset

-- Get by slug
SELECT toolkit_id, slug, name, description, logo_url, category, created_at, updated_at
FROM toolkits t
WHERE t.slug = :slug AND t.is_deprecated = FALSE
```

## Usage

### For Users
1. Navigate to `/integrations` from the main navigation
2. Browse first 10 integrations displayed on load
3. Use search bar to find specific integrations
4. Click "Load More" to see additional integrations
5. Use category tabs to filter by integration type
6. Click "Connect" to link an integration (future feature)

### For Developers
1. **Testing**: Run `python scripts/test_integrations_api.py` to test the API
2. **Customization**: Modify the grid layout in `integrations.html`
3. **Categories**: Add new category tabs in the template
4. **Styling**: Update CSS in `main.css` for custom themes

## Future Enhancements

### Planned Features
- **Real connection status**: Replace mock connected/connect logic with actual integration status
- **Category filtering**: Implement backend filtering by category
- **Integration details**: Modal or page for detailed integration information
- **Quick actions**: Direct workflow creation from integration cards
- **Favorites**: User preference system for marking favorite integrations

### Technical Improvements
- **Caching**: Redis caching for frequently accessed integrations
- **Image optimization**: Lazy loading and optimization for integration logos
- **Analytics**: Track integration views and connections
- **A/B testing**: Test different card layouts and interactions

## Troubleshooting

### Common Issues
1. **No integrations displayed**: Check database connection and `toolkits` table
2. **Search not working**: Verify backend API is running and accessible
3. **Pagination errors**: Check `limit` and `offset` parameters in API calls
4. **Styling issues**: Ensure TailwindCSS is properly loaded

### Debug Steps
1. Check browser console for JavaScript errors
2. Verify API responses in Network tab
3. Test backend API directly with test script
4. Check database for integration data

## Dependencies

- **Frontend**: TailwindCSS, Alpine.js (for dropdowns)
- **Backend**: FastAPI, SQLAlchemy, asyncpg
- **Database**: PostgreSQL with `toolkits` table
- **Testing**: httpx for API testing

---

For more information, see the main [README.md](../README.md) or contact the development team.
