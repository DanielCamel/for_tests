// класс "Вещ. число"
class RealNumber {
    
    protected double value;

    public RealNumber(double value) {
        this.value = value; // инициализация значения 
    }
    
    public double Module() {
        return(Math.abs(value));
    }

    public void PrintParam() {
        System.out.println("Модуль: " + Module());
        System.out.print("Число:" + value);
    }
}

// Класс "Комплексное число" - производный
class ComplexNumber extends RealNumber {

    protected double imagine;

    public ComplexNumber(double real, double imagine) {
        super(real); // инициализация вещ. части через конструктор класса базового
        this.imagine = imagine;
    }

    @Override
    public double Module() {
        return(Math.sqrt(value * value + imagine * imagine));
    }
    @Override
    public void PrintParam() {
        super.PrintParam(); // вызываем метод базового класса
        System.out.println(" + " + imagine + "i");
    }
}

// Основной класс 
public class RK2 {
    public static void main(String[] args){

    // создаём объекты - числа
    RealNumber realNum = new RealNumber(-10.386);
    ComplexNumber complexNum = new ComplexNumber(4.0, 5.0);
    
    // Ссылка на базовый класс
    RealNumber ref;

    // Ссылка на объект базового класса
    ref = realNum;
    ref.PrintParam(); // вызываем метод базового класса через ссылку на объект
    System.out.println(ref.Module());

    // Ссылка на объект производного класса
    ref = complexNum;
    ref.PrintParam(); // вызываем метод производного класса через ссылку на объект
    System.out.println(ref.Module()); 
    
    /*
    * Благодаря полиморфизму вызывается ПЕРЕОПРЕДЕЛЕННЫЙ метод из производного класса 
    ComplexNumber, несмотря на то, что переменная ref имеет тип базового класса RealNumber.
    */
    }
}