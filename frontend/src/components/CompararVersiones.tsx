import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Group, Loader, Select, Stack, Text, Title } from "@mantine/core";
import { api } from "../api/cliente";
import type { Comparacion, Version } from "../api/tipos";

function colorDeLinea(linea: string) {
  if (linea.startsWith("+++") || linea.startsWith("---")) return "dimmed";
  if (linea.startsWith("+")) return "green";
  if (linea.startsWith("-")) return "red";
  if (linea.startsWith("@@")) return "blue";
  return undefined;
}

export default function CompararVersiones({ documentoId }: { documentoId: string }) {
  const [a, setA] = useState<string | null>(null);
  const [b, setB] = useState<string | null>(null);

  const { data: versiones } = useQuery({
    queryKey: ["versiones", documentoId],
    queryFn: () => api<Version[]>(`/documents/${documentoId}/versions/`),
  });

  const { data: comparacion, isFetching } = useQuery({
    queryKey: ["comparar", documentoId, a, b],
    queryFn: () => api<Comparacion>(`/documents/${documentoId}/compare/?a=${a}&b=${b}`),
    enabled: Boolean(a && b),
  });

  const opciones = (versiones ?? []).map((version) => ({
    value: String(version.numero_version),
    label: `Versión ${version.numero_version}`,
  }));

  return (
    <Stack>
      <Title order={3}>Comparar versiones</Title>
      <Group grow>
        <Select label="Versión A (antes)" data={opciones} value={a} onChange={setA} />
        <Select label="Versión B (después)" data={opciones} value={b} onChange={setB} />
      </Group>

      {isFetching && <Loader size="sm" />}

      {comparacion && (
        <Card withBorder>
          {comparacion.diferencias.length === 0 ? (
            <Text c="dimmed">No hay diferencias entre estas versiones.</Text>
          ) : (
            comparacion.diferencias.map((linea, indice) => (
              <Text key={indice} c={colorDeLinea(linea)} ff="monospace" size="sm">
                {linea}
              </Text>
            ))
          )}
        </Card>
      )}
    </Stack>
  );
}