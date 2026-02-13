# Threat Intelligence Frontend

A Next.js application for managing threat intelligence data sources with Supabase integration.

## Features

- **Data Sources Management**: Full CRUD operations for RSS feed data sources
- **Left Sidebar Navigation**: Easy navigation between different sections
- **Real-time Database**: Powered by Supabase for instant updates
- **Responsive UI**: Built with Tailwind CSS
- **TypeScript**: Full type safety throughout the application

## Prerequisites

- Node.js 18+ installed
- A Supabase account and project
- Access to the Supabase database

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Update the `.env.local` file with your Supabase credentials:

```env
NEXT_PUBLIC_SUPABASE_URL=https://ltcgxmifxzgocgbjmqhy.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_actual_anon_key_here
```

**To get your Supabase Anon Key:**
1. Go to your Supabase project dashboard
2. Navigate to Settings > API
3. Copy the "anon" / "public" key
4. Replace `your_actual_anon_key_here` in `.env.local`

### 3. Run the Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
frontend/
├── app/
│   ├── data-sources/       # Data sources CRUD page
│   ├── layout.tsx          # Root layout with sidebar
│   ├── page.tsx            # Dashboard home page
│   └── globals.css         # Global styles
├── components/
│   └── Sidebar.tsx         # Left navigation sidebar
├── lib/
│   └── supabase.ts         # Supabase client configuration
├── types/
│   └── database.ts         # TypeScript type definitions
└── public/                 # Static assets
```

## Database Schema

The application uses the `data_sources` table with the following structure:

```sql
CREATE TABLE data_sources (
  id SERIAL PRIMARY KEY,
  name VARCHAR UNIQUE NOT NULL,
  url VARCHAR UNIQUE NOT NULL,
  active VARCHAR DEFAULT 'true'
);
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint

## Features Roadmap

The sidebar is designed to accommodate additional features:
- ✅ Data Sources Management
- 📋 Articles Dashboard (planned)
- 📊 Analytics & Reports (planned)
- 🔍 Threat Intelligence Viewer (planned)
- ⚙️ Settings (planned)

## Usage

### Adding a Data Source

1. Navigate to "Data Sources" in the sidebar
2. Click "Add Data Source" button
3. Fill in the name and RSS feed URL
4. Set the status (Active/Inactive)
5. Click "Add"

### Editing a Data Source

1. Click "Edit" on any data source row
2. Modify the fields
3. Click "Update"

### Deleting a Data Source

1. Click "Delete" on any data source row
2. Confirm the deletion

### Toggling Active Status

Click on the status badge (Active/Inactive) to quickly toggle the status.

## Troubleshooting

### "Failed to fetch data sources"

- Verify your Supabase credentials in `.env.local`
- Check that the `data_sources` table exists in your Supabase database
- Ensure your Supabase project has Row Level Security (RLS) policies configured properly

### Connection Issues

If you see connection errors:
1. Check your internet connection
2. Verify the Supabase URL is correct
3. Ensure the anon key is valid and has the necessary permissions

## Contributing

When adding new features:
1. Add new pages under the `app/` directory
2. Update the navigation items in `components/Sidebar.tsx`
3. Create TypeScript types in `types/` directory
4. Follow the existing code structure and conventions
