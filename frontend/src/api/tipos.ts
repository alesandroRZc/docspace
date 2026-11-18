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