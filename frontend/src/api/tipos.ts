export type Nivel = "LECTURA" | "EDICION" | "ADMINISTRACION";

export type Documento = {
  id: string;
  espacio: string;
  titulo: string;
  fecha_creacion: string;
  fecha_actualizacion: string;
  mi_permiso: Nivel | null;
  contenido_actual: string;
};