# Supabase Setup Guide

## Getting Your Supabase Credentials

### 1. Get Supabase URL and Anon Key

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Select your project: `ltcgxmifxzgocgbjmqhy`
3. Click on "Settings" (gear icon) in the left sidebar
4. Click on "API" under Project Settings
5. You'll see:
   - **Project URL**: `https://ltcgxmifxzgocgbjmqhy.supabase.co`
   - **anon/public key**: A long string starting with `eyJ...`
6. Copy both values and update `.env.local`

## Row Level Security (RLS) Policies

To allow the frontend to read/write data, you need to set up RLS policies.

### Option 1: Disable RLS (For Development Only)

**⚠️ WARNING: Only use this in development. Never in production!**

Run this SQL in your Supabase SQL Editor:

```sql
ALTER TABLE data_sources DISABLE ROW LEVEL SECURITY;
```

### Option 2: Enable Proper RLS Policies (Recommended)

Run this SQL in your Supabase SQL Editor:

```sql
-- Enable RLS
ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;

-- Allow all operations for authenticated and anonymous users (adjust as needed)
CREATE POLICY "Allow all operations on data_sources"
ON data_sources
FOR ALL
USING (true)
WITH CHECK (true);
```

### Option 3: More Restrictive Policies (Production Ready)

```sql
-- Enable RLS
ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;

-- Allow read access to everyone
CREATE POLICY "Allow public read access"
ON data_sources
FOR SELECT
USING (true);

-- Allow insert for authenticated users only
CREATE POLICY "Allow authenticated insert"
ON data_sources
FOR INSERT
WITH CHECK (auth.role() = 'authenticated');

-- Allow update for authenticated users only
CREATE POLICY "Allow authenticated update"
ON data_sources
FOR UPDATE
USING (auth.role() = 'authenticated')
WITH CHECK (auth.role() = 'authenticated');

-- Allow delete for authenticated users only
CREATE POLICY "Allow authenticated delete"
ON data_sources
FOR DELETE
USING (auth.role() = 'authenticated');
```

## Testing the Connection

After setting up:

1. Make sure `.env.local` has the correct values
2. Run `npm run dev`
3. Navigate to [http://localhost:3000/data-sources](http://localhost:3000/data-sources)
4. You should see your data sources listed

## Common Issues

### "Failed to fetch data sources"

**Cause**: RLS is enabled but no policies exist
**Solution**: Run one of the policy SQL scripts above

### "Invalid API key"

**Cause**: Wrong anon key in `.env.local`
**Solution**: Copy the correct key from Supabase dashboard

### "new row violates row-level security policy"

**Cause**: INSERT policy is too restrictive
**Solution**: Use Option 2 RLS policy for development

## Additional Tables

If you want to manage other tables (articles, rss_items, etc.), you'll need to:

1. Create similar RLS policies for those tables
2. Add TypeScript types in `types/database.ts`
3. Create new pages in `app/` directory
4. Update the sidebar navigation
