#include <FastLED.h>
#include <SoftwareSerial.h>

#define chip_fitas_de_led WS2812B //chipset das fitas de led
#define ordem_de_cores GRB     //ordem dos leds dentro de cada led

#define numero_de_leds 60      //numero de leds por fita
#define numero_de_fitas 3      //numero total de fitas controladas

#define pin_fita_1 4          //pino de dados de cada fita no arduino
#define pin_fita_2 5          
#define pin_fita_3 6          

unsigned long vel_conexao = 9600;

uint8_t brilho_maximo = 220;
uint8_t H = 125;
uint8_t V = 80;
uint8_t S = 1;
uint8_t delay_loop = 10;
uint8_t selectedMode;

uint8_t margem = 5;
uint8_t centerCore = 30;

uint8_t emg = 80;

String serial_comunication;

SoftwareSerial bluetooth(2, 3); //TX, RX (Bluetooth)

uint8_t currentHue = 100;
uint8_t targetHue;

CRGB fita_de_led[numero_de_fitas][numero_de_leds];

void setup() {

  bluetooth.begin(vel_conexao);
  Serial.begin(vel_conexao);
  delay(500);  // Power-up delay

  FastLED.addLeds <chip_fitas_de_led, pin_fita_1, ordem_de_cores> (fita_de_led[0], numero_de_leds);
  FastLED.addLeds <chip_fitas_de_led, pin_fita_2, ordem_de_cores> (fita_de_led[1], numero_de_leds);
  FastLED.addLeds <chip_fitas_de_led, pin_fita_3, ordem_de_cores> (fita_de_led[2], numero_de_leds);

  for(int i = 0; i < numero_de_fitas; i++){
    fill_solid(fita_de_led[i], numero_de_leds, CHSV(0, S, V));
  }
  FastLED.show();
  delay(100);
}

void um_a_um(uint8_t H, uint8_t S, uint8_t V){
  EVERY_N_MILLISECONDS(delay_loop){
    for(uint8_t led = 0; led < numero_de_leds; led ++){
      for (uint8_t fita = 0; fita < numero_de_fitas; fita++){
        fita_de_led[fita][led].setHSV(H, S, V);
      }
      FastLED.show();
    }
  }
  currentHue = H;
}

void todos_de_uma_vez(uint8_t H, uint8_t S, uint8_t V){
  for (uint8_t fita = 0; fita < numero_de_fitas; fita++){
    fill_solid(fita_de_led[fita], numero_de_leds, CHSV(H, S, V));
  }
  FastLED.show();
  currentHue = H;
}

void gradiente(uint8_t targetHue, uint8_t S, uint8_t V) {
  uint8_t increment = 1;
  int diff = currentHue - targetHue; //se diff > 0, então currentHue>targetHue, logo devemos dimunuir o current até o target (currentHue--)| se diff < 0 então currentHue < targetHue
  if (abs(diff) > 153){
    increment = 2;
  }
  while (currentHue != targetHue) {
    // Increment or decrement the hue smoothly
    if (diff > 0) {
      currentHue = currentHue - increment;
    } 
    else if (diff < 0) {
      currentHue = currentHue + increment;  // Increase hue by 1
    }
      // Set all the LEDs to the new hue
    for (uint8_t fita = 0; fita < numero_de_fitas; fita++){
      fill_solid(fita_de_led[fita], numero_de_leds, CHSV(currentHue, S, V));
    }
    FastLED.show();
  }
  currentHue = targetHue;
}

void a_partir_do_centro(uint8_t H, uint8_t S, uint8_t V){
  for (int led = 0; led < numero_de_leds/(numero_de_leds/centerCore); led++){
    for (int fita = 0; fita <= numero_de_fitas; fita++){
      fita_de_led[fita][centerCore+led].setHSV(H, S, min(V+50, brilho_maximo));
      fita_de_led[fita][centerCore-led].setHSV(H, S, min(V+50, brilho_maximo));
    }
    FastLED.show();
    delay(20); //20ms = 780 total
  }
  currentHue = H;
}

void processar_string_recebida(String input) {

  // Verifica se a string recebida está no formato esperado
  if (input.charAt(0) == '(' && input.charAt(input.length() - 1) == ')') { //sempre recebe (x,xxx,xxx,xxx) onde xxx pode variar entre x, xx e xxx

    // Remove os parênteses
    input = input.substring(1, input.length() - 1); //resulta em x,xxx,xxx,xxx index = 0 1 2 3 4 5 6 7 8 9 10 11 12
    
    // Divide a string pelos espaços e vírgulas
    int firstComma  = input.indexOf(',');
    int secondComma = input.indexOf(',', firstComma + 1);
    int thirdComma = input.indexOf(',', secondComma + 1);
    
    // Extrai os números como strings
    String mode = input.substring(0,firstComma);
    String num1String = input.substring(firstComma + 1, secondComma);
    String num2String = input.substring(secondComma + 1, thirdComma);
    String num3String = input.substring(thirdComma + 1);

    // Converte as strings para inteiros e salva nas variáveis globais
    selectedMode = mode.toInt();
    H = num1String.toInt();
    S = num2String.toInt();
    V = min(num3String.toInt(),150); //configura o valor máximo do brilho para 200 | ex: se V for 150 , v = 150 ... se v = 255, v será igual a 200
  } 
}

void executarModo(uint8_t mode, uint8_t H, uint8_t S, uint8_t V) {
  switch (mode) {
    case 1:
      um_a_um(H, S, V);
      break;
    case 2:
      todos_de_uma_vez(H, S, V);
      break;
    case 3:
      gradiente(H, S, V);
      break;
    case 4:
      a_partir_do_centro(H, S, V);
      break;
    default:
      a_partir_do_centro(H, S, V);
  }
}

bool a = false;

void loop() {
  // Verifica se há dados na serial principal
  if (Serial.available() > 0) {
    serial_comunication = Serial.readStringUntil('\n');
    processar_string_recebida(serial_comunication);
    executarModo(selectedMode, H, S, V); // Chama a função de execução do modo
  }
  // Verifica se há dados via bluetooth
  else if (bluetooth.available() > 0) {
    serial_comunication = bluetooth.readStringUntil('\n');
    processar_string_recebida(serial_comunication);  // Processa o comando recebido
    executarModo(selectedMode, H, S, V);  // Chama a função de execução do modo
  }
  else if (a == true){ 
    //faseoffset vai de 0 a 255, sendo 127 meia onda | time base vai de 0 a 1000ms pois uma onde dura 1 segundo, portanto meia onda é 500ms poe exemplo
    uint8_t brilhoEmg = beatsin8(emg, V+12, min(V+50, brilho_maximo), 0, 0);
    uint8_t palete = beatsin8(emg, currentHue-8, currentHue+8, 0, 0);

    for (int fita = 0; fita < numero_de_fitas; fita ++){
      for (int led = 0; led < numero_de_leds; led++){
        if (led >= centerCore - margem && led <= centerCore + margem){   //centerCore = 15 | margem = 2
          fita_de_led[fita][led].setHSV(palete, S, brilhoEmg);
        }
        else if (led < (centerCore - margem)){
          fita_de_led[fita][led].setHSV(palete, S, V);
        }
        else if (led > (centerCore + margem)){
          fita_de_led[fita][led].setHSV(palete, S, V);
        }
      }
    }
    FastLED.show();
  }
}

