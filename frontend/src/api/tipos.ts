export type Nivel = "LECTURA" | "EDICION" | "ADMINISTRACION";

export type Documento = {
  id: string;
  espacio: string;
  titulo: string;
  fecha_creacion: string;
  fecha_actualizacion: string;
  mi_permiso: Nivel | null;
  contenido_actual: string;

  
}
const JERARQUIA: Record<Nivel, number> = {
  LECTURA: 1,
  EDICION: 2,
  ADMINISTRACION: 3,
};

export function tieneNivel(nivel: Nivel | null, minimo: Nivel) {
  if (nivel === null) return false;
  return JERARQUIA[nivel] >= JERARQUIA[minimo];
}

export type Version = {
  id: string;
  numero_version: number;
  contenido: string;
  autor: string;
  fecha_creacion: string;
  restaurada_desde: string | null;
};

export type Comparacion = {
  version_a: number;
  version_b: number;
  diferencias: string[];
};

export type Usuario = {
  id: string;
  email: string;
  username: string;
  nombre: string;
  tipo_cuenta: "GESTOR" | "COLABORADOR";
};

export type Espacio = {
  id: string;
  nombre: string;
  gestor: string;
  fecha_creacion: string;
};