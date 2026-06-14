"""
Máquina de estados da peça para o Quality Gate.

Fluxo completo:
    idle → identified → validating_v1 → validating_v2 → waiting_bench_b → validating_v3 → approved
                                ↕ rework_v1          ↕ rework_v2                    ↕ rework_v3
    Qualquer validating_vN → identified  (falso positivo)
"""

# Mapa de estado → lista de estados destino permitidos
VALID_TRANSITIONS: dict[str, list[str]] = {
    # Criação e identificação
    "idle": ["identified"],
    # Identificada → inicia inspeção
    "identified": ["validating_v1"],
    # V1: resultado OK avança, NOK vai para retrabalho; falso positivo volta
    "validating_v1": ["validating_v2", "rework_v1", "identified"],
    # Retrabalho V1 → re-inspecionar
    "rework_v1": ["validating_v1"],
    # V2: resultado OK → aguarda bancada B; NOK → retrabalho; falso positivo volta
    "validating_v2": ["waiting_bench_b", "rework_v2", "identified"],
    # Retrabalho V2 → re-inspecionar
    "rework_v2": ["validating_v2"],
    # Aguardando Bancada B — operador libera
    "waiting_bench_b": ["validating_v3"],
    # V3: resultado OK → aprovada; NOK → retrabalho; falso positivo volta
    "validating_v3": ["approved", "rework_v3", "identified"],
    # Retrabalho V3 → re-inspecionar
    "rework_v3": ["validating_v3"],
    # Terminais — sem transições de saída
    "approved": [],
    "rejected": [],
}

# Mapeamento de tipo de validação para estado de validação correspondente
_VALIDATION_STATES: dict[str, str] = {
    "v1": "validating_v1",
    "v2": "validating_v2",
    "v3": "validating_v3",
}

# Mapeamento de estado de validação para tipo
_STATE_TO_VALIDATION: dict[str, str] = {v: k for k, v in _VALIDATION_STATES.items()}

# Mapeamento de tipo de validação para estado de retrabalho
_REWORK_STATES: dict[str, str] = {
    "v1": "rework_v1",
    "v2": "rework_v2",
    "v3": "rework_v3",
}

# Estados terminais (sem transição possível)
_TERMINAL_STATES: frozenset[str] = frozenset(["approved", "rejected"])

# Estados de validação em curso
_VALIDATING_STATES: frozenset[str] = frozenset(["validating_v1", "validating_v2", "validating_v3"])

# Estados de retrabalho em curso
_REWORK_STATES_SET: frozenset[str] = frozenset(["rework_v1", "rework_v2", "rework_v3"])


class PieceStateMachine:
    """Controla as transições de estado de uma peça no quality gate.

    Uso:
        sm = PieceStateMachine()
        if sm.can_transition("idle", "identified"):
            new_state = sm.transition("idle", "identified")
    """

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Verifica se a transição de from_state para to_state é válida.

        Args:
            from_state: Estado atual da peça.
            to_state: Estado destino desejado.

        Returns:
            True se a transição é permitida, False caso contrário.
        """
        allowed = VALID_TRANSITIONS.get(from_state, [])
        return to_state in allowed

    def transition(self, from_state: str, to_state: str) -> str:
        """Executa a transição de estado, retornando o novo estado.

        Args:
            from_state: Estado atual da peça.
            to_state: Estado destino desejado.

        Returns:
            O novo estado (to_state) se a transição for válida.

        Raises:
            ValueError: Se a transição não for permitida.
        """
        if not self.can_transition(from_state, to_state):
            raise ValueError(
                f"Transição inválida: {from_state!r} → {to_state!r}. "
                f"Transições permitidas: {VALID_TRANSITIONS.get(from_state, [])}"
            )
        return to_state

    def get_validation_type(self, status: str) -> str | None:
        """Retorna o tipo de validação a partir do status de validação.

        Exemplo: "validating_v1" → "v1"

        Args:
            status: Estado atual da peça.

        Returns:
            String "v1", "v2" ou "v3", ou None se não for um estado de validação.
        """
        return _STATE_TO_VALIDATION.get(status)

    def get_rework_state(self, validation_type: str) -> str:
        """Retorna o estado de retrabalho correspondente ao tipo de validação.

        Exemplo: "v1" → "rework_v1"

        Args:
            validation_type: Tipo da validação ("v1", "v2" ou "v3").

        Returns:
            String com o estado de retrabalho correspondente.

        Raises:
            KeyError: Se validation_type for inválido.
        """
        if validation_type not in _REWORK_STATES:
            raise KeyError(
                f"Tipo de validação inválido: {validation_type!r}. Esperado: v1, v2 ou v3."
            )
        return _REWORK_STATES[validation_type]

    def get_next_validation(self, current_validation: str) -> str | None:
        """Retorna o próximo estado após validação OK.

        Mapeamento:
            v1 → "validating_v2"
            v2 → "waiting_bench_b"
            v3 → "approved"

        Args:
            current_validation: Tipo da validação atual ("v1", "v2" ou "v3").

        Returns:
            O próximo estado destino, ou None se current_validation for inválido.
        """
        _next_map: dict[str, str] = {
            "v1": "validating_v2",
            "v2": "waiting_bench_b",
            "v3": "approved",
        }
        return _next_map.get(current_validation)

    def is_terminal(self, status: str) -> bool:
        """Verifica se o status é um estado terminal (sem mais transições).

        Args:
            status: Estado atual da peça.

        Returns:
            True se o status for "approved" ou "rejected".
        """
        return status in _TERMINAL_STATES

    def is_validating(self, status: str) -> bool:
        """Verifica se a peça está em um estado de validação ativa.

        Args:
            status: Estado atual da peça.

        Returns:
            True se status for validating_v1, validating_v2 ou validating_v3.
        """
        return status in _VALIDATING_STATES

    def is_rework(self, status: str) -> bool:
        """Verifica se a peça está em um estado de retrabalho.

        Args:
            status: Estado atual da peça.

        Returns:
            True se status for rework_v1, rework_v2 ou rework_v3.
        """
        return status in _REWORK_STATES_SET
