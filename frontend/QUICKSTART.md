# Quick Start Guide

## ✅ What's Been Created

Your Next.js frontend application is ready with:

1. **Complete CRUD Interface** for data_sources table
2. **Left Sidebar Menu** for easy navigation (expandable for future features)
3. **Supabase Integration** for real-time database access
4. **TypeScript** for type safety
5. **Tailwind CSS** for styling
6. **Responsive Design** that works on all devices

## 🚀 Getting Started

### Step 1: Get Your Supabase Anon Key

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Select your project
3. Click **Settings** → **API**
4. Copy the **anon/public** key
5. Paste it into `.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://ltcgxmifxzgocgbjmqhy.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_copied_key_here
```

### Step 2: Set Up Database Permissions

Open your Supabase SQL Editor and run:

```sql
-- For development (simple approach)
ALTER TABLE data_sources DISABLE ROW LEVEL SECURITY;
```

Or for production-ready setup, see `SUPABASE_SETUP.md`.

### Step 3: Start the Development Server

```bash
cd frontend
npm run dev
```

### Step 4: Open Your Browser

Visit [http://localhost:3000](http://localhost:3000)

## 📁 Project Structure

```
frontend/
├── app/
│   ├── data-sources/       ← Data sources CRUD page
│   │   └── page.tsx
│   ├── layout.tsx          ← Layout with sidebar
│   ├── page.tsx            ← Dashboard home
│   └── globals.css
├── components/
│   └── Sidebar.tsx         ← Navigation menu
├── lib/
│   └── supabase.ts         ← Database client
├── types/
│   └── database.ts         ← TypeScript types
└── .env.local              ← Configuration (⚠️ add your key!)
```

## 🎯 Features

### Data Sources Page (`/data-sources`)

- ✅ View all data sources in a table
- ✅ Add new RSS feeds
- ✅ Edit existing sources
- ✅ Delete sources (with confirmation)
- ✅ Toggle active/inactive status with one click
- ✅ Click URLs to open in new tab

### Navigation

The sidebar includes:
- **Dashboard** - Overview page (ready for stats)
- **Data Sources** - Manage RSS feeds
- *More sections can be easily added*

## 🔧 Common Tasks

### Add a New Menu Item

Edit `components/Sidebar.tsx`:

```typescript
const navigation = [
  { name: "Dashboard", href: "/" },
  { name: "Data Sources", href: "/data-sources" },
  { name: "Your New Page", href: "/your-new-page" }, // Add this
];
```

### Create a New Page

```bash
mkdir app/your-new-page
# Create app/your-new-page/page.tsx
```

### Test the Build

```bash
npm run build
```

## 🐛 Troubleshooting

### "Failed to fetch data sources"
- Check `.env.local` has the correct Supabase key
- Verify RLS policies are set up (see SUPABASE_SETUP.md)
- Check browser console for detailed errors

### Port 3000 Already in Use
```bash
# Use a different port
npm run dev -- -p 3001
```

### Types Not Working
```bash
# Restart TypeScript server in your editor
# Or run:
npm run build
```

## 📚 Additional Documentation

- `README.md` - Full project documentation
- `SUPABASE_SETUP.md` - Detailed Supabase configuration guide

## 🎨 Next Steps

1. Get your Supabase anon key
2. Update `.env.local`
3. Run the dev server
4. Start managing your data sources!

Future enhancements you might want to add:
- Articles viewer
- Analytics dashboard
- User authentication
- Export/import functionality
- Bulk operations
