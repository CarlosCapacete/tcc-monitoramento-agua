 //==========================================
// TESTE DE PULSOS - SENSOR DE VAZÃO ZJ-S201
// Placa: XIAO ESP32-C6
// Pino do Sensor: D2
// ==========================================

// Define o pino que vai receber o sinal do sensor
#define PINO_SENSOR D2

// Variável que vai contar os pulsos. 
// A palavra 'volatile' avisa o compilador que ela muda de repente (dentro da interrupção)
volatile int contadorPulsos = 0;

// Função de Interrupção: executada toda vez que o sensor gerar um pulso
// IRAM_ATTR faz essa função rodar na memória RAM interna, que é mais rápida
void IRAM_ATTR contarPulso() {
  contadorPulsos++;
}

void setup() {
  // Inicia a comunicação Serial para podermos ver os dados no computador
  Serial.begin(115200);
  
  // Configura o pino do sensor como entrada com pull-up interno ativado
  // (O resistor de 10k externo ajuda, mas ativar o interno é uma segurança a mais)
  pinMode(PINO_SENSOR, INPUT_PULLUP);
  
  // Anexa a interrupção ao pino do sensor
  // FALLING significa que ele vai contar quando o sinal cair de 3.3V para 0V
  attachInterrupt(digitalPinToInterrupt(PINO_SENSOR), contarPulso, FALLING);
  
  Serial.println("--- Teste de Sensor de Vazao Iniciado ---");
  Serial.println("Aguardando pulsos...");
}

void loop() {
  // A cada 1 segundo, mostramos quantos pulsos ocorreram
  delay(1000);
  
  // Desliga a interrupção temporariamente para ler o valor com segurança
  noInterrupts();
  int pulsos = contadorPulsos;
  contadorPulsos = 0; // Zera o contador para a próxima medição
  interrupts();
  
  // Mostra o resultado no Monitor Serial
  Serial.print("Pulsos por segundo: ");
  Serial.println(pulsos);
  
  // Se não houver pulsos, avisa que está tudo parado
  if (pulsos == 0) {
    Serial.println("Nenhum pulso detectado. Tente assoprar o sensor ou girar a turbina com o dedo.");
  }
}

