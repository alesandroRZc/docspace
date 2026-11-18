const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export function guardarToken(token: string) {
  localStorage.setItem("token", token);
}

export function obtenerToken() {
  return localStorage.getItem("token");
}

export function cerrarSesion() {
  localStorage.removeItem("token");
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = obtenerToken();

  const respuesta = await fetch(`${API_URL}${ruta}`, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opciones.headers,
    },
  });

  if (respuesta.status === 401) {
    cerrarSesion();
  }

  if (!respuesta.ok) {
    const error = await respuesta.json().catch(() => ({}));
    throw new Error(error.detail ?? "Ocurrió un error inesperado.");
  }

  if (respuesta.status === 204) {
    return undefined as T;
  }

  return respuesta.json();
}