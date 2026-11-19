import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Alert, Badge, Button, Card, Container, Group, Loader, Stack, Text, Title } from "@mantine/core";
import { api, cerrarSesion } from "../api/cliente";
import type { Documento, Usuario } from "../api/tipos";
import PanelGestor from "../components/PanelGestor";

export default function DocumentosPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: documentos, isLoading, error } = useQuery({
    queryKey: ["documentos"],
    queryFn: () => api<Documento[]>("/documents/"),
  });

  const { data: yo } = useQuery({
    queryKey: ["yo"],
    queryFn: () => api<Usuario>("/auth/me/"),
  });

  return (
    <Container py="xl">
      <Group justify="space-between" mb="lg">
        <div>
          <Title>Mis documentos</Title>
          {yo && (
            <Text c="dimmed" size="sm">
              {yo.nombre} · {yo.tipo_cuenta === "GESTOR" ? "Gestor" : "Colaborador"}
            </Text>
          )}
        </div>        
        <Button
          variant="light"
          color="red"
          onClick={() => {
            cerrarSesion();
            queryClient.clear();
            navigate("/login");
          }}
        >
          Cerrar sesión
        </Button>
      </Group>

      {yo?.tipo_cuenta === "GESTOR" && <PanelGestor yo={yo} />}

      {isLoading && <Loader />}
      {error && <Alert color="red">No se pudieron cargar los documentos.</Alert>}
      {documentos && documentos.length === 0 && <Text c="dimmed">No tienes documentos visibles.</Text>}

      <Stack>
        {documentos?.map((documento) => (
          <Card key={documento.id} withBorder component={Link} to={`/documentos/${documento.id}`}>
            <Group justify="space-between">
              <Text fw={600}>{documento.titulo}</Text>
              <Badge>{documento.mi_permiso}</Badge>
            </Group>
          </Card>
        ))}
      </Stack>
    </Container>
  );
}