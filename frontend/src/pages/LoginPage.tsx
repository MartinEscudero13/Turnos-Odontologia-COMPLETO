import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { Field } from '../components/Field';

export function LoginPage(): JSX.Element {
  const { session, login } = useAuth();
  const navigate = useNavigate();
  const [tenantSlug, setTenantSlug] = useState('demo');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  if (session) {
    return <Navigate to="/app" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setIsLoading(true);
    const result = await login({ tenantSlug, email, password });
    setIsLoading(false);
    if (!result.ok) {
      setError(result.error ?? 'No pudimos iniciar sesión.');
      return;
    }
    navigate('/app', { replace: true });
  }

  return (
    <section className="login-panel" aria-labelledby="login-title">
      <div className="login-heading">
        <p className="eyebrow">Acceso interno</p>
        <h1 id="login-title">Tu agenda empieza acá.</h1>
        <p>Ingresá con las credenciales del consultorio. El paciente no necesita cuenta en v1.</p>
      </div>

      <form className="login-form" onSubmit={handleSubmit} noValidate>
        <Field
          label="Consultorio"
          hint="El identificador del tenant, por ejemplo demo."
          autoComplete="organization"
          value={tenantSlug}
          onChange={(event) => setTenantSlug(event.target.value)}
          required
        />
        <Field
          label="Email"
          type="email"
          autoComplete="username"
          inputMode="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <Field
          label="Contraseña"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error ? (
          <p className="form-error" role="alert" aria-live="polite">
            {error}
          </p>
        ) : null}
        <Button type="submit" isLoading={isLoading} className="button-full">
          Entrar al panel
        </Button>
      </form>

      <div className="login-foot">
        <Link className="quiet-link" to="/">
          Volver al inicio
        </Link>
        <span>Acceso para recepción, odontología y administración.</span>
      </div>
    </section>
  );
}
