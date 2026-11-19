import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Anchor, Badge, Button, Container, Group, Loader, Stack, Textarea, Title, Text } from "@mantine/core";
import { api } from "../api/cliente";
import { tieneNivel, type Documento } from "../api/tipos";
import HistorialVersiones from "../components/HistorialVersiones";
import CompararVersiones from "../components/CompararVersiones";
import GestionAcceso from "../components/GestionAcceso";

export default function DocumentoPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [contenido, setContenido] = useState("");

  const { data: documento, isLoading, error } = useQuery({
    queryKey: ["documento", id],
    queryFn: () => api<Documento>(`/documents/${id}/`),
  });

  useEffect(() => {
    if (documento) {
      setContenido(documento.contenido_actual);
    }
  }, [documento]);

  const guardar = useMutation({
    mutationFn: () =>
      api(`/documents/${id}/save/`, {
        method: "POST",
        body: JSON.stringify({ contenido }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documento", id] });
      queryClient.invalidateQueries({ queryKey: ["versiones", id] });
    },
  });

  const eliminar = useMutation({
    mutationFn: () => api(`/documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
      navigate("/documentos");
    },
  });

  if (isLoading) return <Container py="xl"><Loader /></Container>;
  if (error || !documento) {
    return (
      <Container py="xl">
        <Alert color="red">Documento no encontrado.</Alert>
        <Anchor component={Link} to="/documentos">← Volver</Anchor>
      </Container>
    );
  }

  const puedeEditar = tieneNivel(documento.mi_permiso, "EDICION");
  const puedeAdministrar = tieneNivel(documento.mi_permiso, "ADMINISTRACION");

  return (
    <Container py="xl">
      <Stack>
        <Anchor component={Link} to="/documentos">← Volver a mis documentos</Anchor>

        <Group justify="space-between">
          <Title order={2}>{documento.titulo}</Title>
          <Badge size="lg">{documento.mi_permiso}</Badge>
        </Group>
        <Text size="sm" c="dimmed">Creado por {documento.creador_nombre}</Text>

        <Textarea
          value={contenido}
          onChange={(evento) => setContenido(evento.currentTarget.value)}
          readOnly={!puedeEditar}
          autosize
          minRows={10}
        />

        {guardar.isSuccess && <Alert color="green">Versión guardada.</Alert>}
        {guardar.error && <Alert color="red">{guardar.error.message}</Alert>}

        <Group justify="flex-end">
          {puedeAdministrar && (
            <Button
              color="red"
              variant="light"
              loading={eliminar.isPending}
              onClick={() => {
                if (window.confirm("¿Eliminar este documento? Su historial se conservará.")) {
                  eliminar.mutate();
                }
              }}
            >
              Eliminar documento
            </Button>
          )}
          {puedeEditar && (
            <Button onClick={() => guardar.mutate()} loading={guardar.isPending}>
              Guardar nueva versión
            </Button>
          )}
        </Group>

        <HistorialVersiones documentoId={documento.id} miPermiso={documento.mi_permiso} />
        <CompararVersiones documentoId={documento.id} />
        {puedeAdministrar && <GestionAcceso documento={documento} />}
      </Stack>
    </Container>
  );
}