# Пошаговый курс "компилятор с нуля"

Здесь лежит исходный код курса. Сам курс [на YouTube](https://youtube.com/playlist?list=PLcBfaByu9Do8)

## Начать работу:
- На [Windows](#установка-на-windows)
- На [Linux](#установка-на-linux)
- ~~На [MacOS]()~~ (только VM / docker)

## Вышедшие части:
1. [простейший компилятор чисел](lesson01/README.md)
2. [компилятор сумм](lesson02/README.md)
3. [полноценная арифметика](lesson03/README.md)
4. [переменные в стеке](lesson04/README.md)
5. [циклы и ветвления](lesson05/README.md)
6. [Функции](lesson06/README.md)

---
## Установка на Windows

#### 1. Открыть cmd 
#### 2. Ввести:
```cmd
wsl --install
```
#### 3. Перезгрузить компьютер, если раньше не был установлен wls
#### 4. ввести в cmd 
```cmd
wsl
```
### 5. В появившейся оболочке ввести 
```shell
sudo apt update && sudo apt install python3 gcc nasm make git -y
```
### 6. Клонировать репозиторий:
```shell
git clone https://github.com/the-lenoz/compiler_lessons.git
```
### 7. Смотреть инструкцию запуска каждого урока
`lessonXX/README.md`

###

_Нативного бэкенда под Windows-toolchain пока нет._

---
## Установка на Linux
### (Debian/Ubuntu); в прочих дистрибутивах пакеты ставятся иначе

### 1. В терминале ввести 
```shell
sudo apt update && sudo apt install python3 gcc nasm make git -y
```
### 2. Клонировать репозиторий:
```shell
git clone https://github.com/the-lenoz/compiler_lessons.git
```
### 3. Смотреть инструкцию запуска каждого урока
`lessonXX/README.md`
