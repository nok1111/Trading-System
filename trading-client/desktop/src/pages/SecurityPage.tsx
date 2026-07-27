import { Shield, Lock, EyeOff, Ban } from "lucide-react";

export function SecurityPage() {
  return (
    <div className="p-5 space-y-4 max-w-[700px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Seguridad</h2>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Shield size={18} className="text-[var(--color-success)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Cifrado de Credenciales</h3>
        </div>
        <p className="text-[12px] text-[var(--color-text-muted)]">
          Todas las API Keys se cifran con Fernet (AES-128-CBC) antes de almacenarse en la base de datos local.
          Las credenciales nunca se envían al AI Server ni se exponen en el frontend.
        </p>
      </div>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Lock size={18} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Restricciones de Permisos</h3>
        </div>
        <ul className="text-[12px] text-[var(--color-text-muted)] space-y-1.5 list-disc ml-5">
          <li>Solo se permiten API Keys con permisos de lectura y trading</li>
          <li className="text-[var(--color-danger)] font-semibold">Está prohibido conectar credenciales con permiso de retiro</li>
          <li>La conexión puede comenzar en modo READ_ONLY por seguridad</li>
          <li>El permiso de trading se habilita manualmente desde la configuración del broker</li>
        </ul>
      </div>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <EyeOff size={18} className="text-[var(--color-warning)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Privacidad de Datos</h3>
        </div>
        <ul className="text-[12px] text-[var(--color-text-muted)] space-y-1.5 list-disc ml-5">
          <li>Las API Keys no se almacenan en el frontend (localStorage, sessionStorage, cookies)</li>
          <li>Después de guardar, las credenciales no se muestran nuevamente</li>
          <li>Los logs nunca contienen secretos ni credenciales</li>
          <li>El AI Server recibe únicamente datos de mercado anonimizados</li>
        </ul>
      </div>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Ban size={18} className="text-[var(--color-danger)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Acciones Prohibidas</h3>
        </div>
        <ul className="text-[12px] text-[var(--color-text-muted)] space-y-1.5 list-disc ml-5">
          <li>No se simulan conexiones falsas de brokers</li>
          <li>No se ejecutan trades directamente desde respuestas del AI Server</li>
          <li>No se envían API Keys ni secrets al AI Server</li>
          <li>No se muestran API Secrets después de guardar</li>
        </ul>
      </div>
    </div>
  );
}
