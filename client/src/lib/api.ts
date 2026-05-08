const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')

export function apiUrl(pathname: string) {
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`

  if (!configuredApiBaseUrl) {
    return `/api${normalizedPath}`
  }

  return `${configuredApiBaseUrl}${normalizedPath}`
}
