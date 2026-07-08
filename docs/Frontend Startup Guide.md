# Frontend Startup Guide

## 1. Enter the frontend directory

```powershell
cd D:/Dev-PCE/Source/frontend
```

## 2. Start the frontend service

```powershell
npm run dev
```

The dev script is fixed to:

```json
"dev": "vite --host localhost --port 5173"
```

Vite starts on `localhost` and prefers port `5173`.

## 3. Confirm the active Local address

After startup, use only the `Local` address printed by the Vite console.

If the console shows:

```text
Local: http://localhost:5173/
```

then the Enterprise OS pages are:

```text
http://localhost:5173/#/process-center
http://localhost:5173/#/work-center
http://localhost:5173/#/organization
http://localhost:5173/#/dashboard
http://localhost:5173/#/analytics
http://localhost:5173/#/admin
```

If the console shows:

```text
Local: http://localhost:5174/
```

then use `5174` for every Enterprise OS page in that dev session:

```text
http://localhost:5174/#/process-center
http://localhost:5174/#/work-center
http://localhost:5174/#/organization
http://localhost:5174/#/dashboard
http://localhost:5174/#/analytics
http://localhost:5174/#/admin
```

Do not mix ports. If the active Vite service is on `5173`, do not open `5174`. If the active Vite service is on `5174`, do not open `5173`.

## 4. Prefer port 5173

If Vite switches to `5174`, it usually means another frontend dev server is still using `5173`.

Recommended action:

1. Stop the old frontend dev service.
2. Run `npm run dev` again.
3. Confirm the console returns to `Local: http://localhost:5173/`.

The root page redirects to:

```text
http://localhost:5173/#/process-center
```

## 5. Verify pages with one port

Use the same port for all checks.

For example, if Vite prints `Local: http://localhost:5173/`, verify:

```text
http://localhost:5173/#/process-center
http://localhost:5173/#/work-center
http://localhost:5173/#/organization
```

If Vite prints `Local: http://localhost:5174/`, verify the same routes on `5174`.

## 6. Fix ERR_CONNECTION_REFUSED

If the browser shows `ERR_CONNECTION_REFUSED`:

1. Confirm the frontend service is still running.
2. Start it again with `npm run dev`.
3. Check the Vite console for the actual port.
4. Open the URL printed by Vite.
5. Do not mix `5173` and `5174`.
6. If another process is using `5173`, stop the old frontend service and restart Vite.
7. Use the alternate Vite port only when the console explicitly shows it.
8. If `127.0.0.1` cannot be reached, use `localhost`.

## 7. Current frontend origin

In development mode, the browser console prints:

```text
Current Frontend Origin: http://localhost:5173
```

Use that origin plus the hash route, for example:

```text
http://localhost:5173/#/process-center
```

Do not open the Enterprise OS pages before the Vite server is running.
