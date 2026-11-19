import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Alert, Anchor, Button, Container, Paper, PasswordInput, SegmentedControl, Stack, Text, TextInput, Title,
} from "@mantine/core";
import { api, guardarToken } from "../api/cliente";

type RespuestaLogin = { access: string; refresh: string };

export default function RegistroPage() {
  const navigate = useNavigate();
  const [nombre, setNombre] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tipoCuenta, setTipoCuenta] = useState("COLABORADOR");

  const registro = useMutation({
    mutationFn: async () => {
      await api("/auth/register/", {
        method: "POST",
        body: JSON.stringify({ nombre, username, email, password, tipo_cuenta: tipoCuenta }),
      });
      return api<RespuestaLogin>("/auth/login/", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
    },
    onSuccess: (datos) => {
      guardarToken(datos.access);
      navigate("/documentos");
    },
  });

  return (
    <Container size={420} py="xl">
      <Title ta="center" mb="lg">Crear cuenta</Title>
      <Paper withBorder shadow="sm" p="lg" radius="md">
        <form
          onSubmit={(evento) => {
            evento.preventDefault();
            registro.mutate();
          }}
        >
          <Stack>
            <div>
              <Text size="sm" fw={500} mb={4}>Tipo de cuenta</Text>
              <SegmentedControl
                fullWidth
                value={tipoCuenta}
                onChange={setTipoCuenta}
                data={[
                  { label: "Colaborador", value: "COLABORADOR" },
                  { label: "Gestor", value: "GESTOR" },
                ]}
              />
            </div>
            <TextInput label="Nombre" value={nombre} onChange={(e) => setNombre(e.currentTarget.value)} required />
            <TextInput label="Usuario" autoComplete="off"  value={username} onChange={(e) => setUsername(e.currentTarget.value)} required />
            <TextInput label="Correo electrónico" type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.currentTarget.value)} required />
            <PasswordInput
              label="Contraseña" autoComplete="new-password" description="Mínimo 8 caracteres" value={password} onChange={(e) => setPassword(e.currentTarget.value)} required/>
            {registro.error && <Alert color="red">{registro.error.message}</Alert>}
            <Button type="submit" loading={registro.isPending}>Crear cuenta</Button>
            <Anchor component={Link} to="/login" ta="center" size="sm">
              ¿Ya tienes cuenta? Inicia sesión
            </Anchor>
          </Stack>
        </form>
      </Paper>
    </Container>
  );
}