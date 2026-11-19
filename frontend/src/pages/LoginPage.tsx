import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert, Anchor, Button, Container, Paper, PasswordInput, Stack, TextInput, Title } from "@mantine/core";
import { api, guardarToken } from "../api/cliente";
import { Link, useNavigate } from "react-router-dom";

type RespuestaLogin = {
  access: string;
  refresh: string;
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () =>
      api<RespuestaLogin>("/auth/login/", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    onSuccess: (datos) => {
      guardarToken(datos.access);
      navigate("/documentos");
    },
  });

  return (
    <Container size={420} py="xl">
      <Title ta="center" mb="lg">DocSpace</Title>
      <Paper withBorder shadow="sm" p="lg" radius="md">
        <form
          onSubmit={(evento) => {
            evento.preventDefault();
            login.mutate();
          }}
        >
          <Stack>
            <TextInput
              label="Correo electrónico"
              value={email}
              onChange={(evento) => setEmail(evento.currentTarget.value)}
              required
            />
            <PasswordInput
              label="Contraseña"
              value={password}
              onChange={(evento) => setPassword(evento.currentTarget.value)}
              required
            />
            {login.error && <Alert color="red">Correo o contraseña incorrectos.</Alert>}
            <Button type="submit" loading={login.isPending}>
              Iniciar sesión
            </Button>   
            <Anchor component={Link} to="/registro" ta="center" size="sm">
              ¿No tienes cuenta? Regístrate
            </Anchor>
          </Stack>
        </form>
      </Paper>
    </Container>
  );
}