import java.util.*;
class MyTimer {
	Date d=new Date();
	public void printTime(String text)
	{
		System.out.println(text+": "+(new Date().getTime()-d.getTime())+" ms");
	}
}
public class Test1 {

	public static void main(String[] args) {
		// TODO Auto-generated method stub
		HashSet <Integer> hS=new HashSet <Integer>();
		ArrayList <Integer> arr=new ArrayList <Integer>();
		Random r=new Random();
		int n1=1000000;
		for(n1=100000; n1<=1000000; n1+=100000)
		{
			hS.clear(); arr.clear();
			System.out.println("n="+n1);
		MyTimer Ob1=new MyTimer();
		for(int i=0; i<n1; i++)
			hS.add(r.nextInt());
		Ob1.printTime("Добавление  в хэш-таблицу");
		MyTimer Ob2=new MyTimer();
		for(int i=0; i<n1; i++)
			arr.add(r.nextInt());
		Ob2.printTime("Добавление к массиву");
		}
		System.out.println("size(хэша)="+hS.size()+ " size(массива)="+arr.size());
		
		
		
		//int n2=10000;
		for(int n2=1000; n2<=5000; n2+=1000)
		{
			System.out.println("m="+n2);
		MyTimer Ob3=new MyTimer();
		for(int i=0; i<n2; i++)
			hS.contains(r.nextInt());
		Ob3.printTime("Поиск в хэш-таблице");
	
		MyTimer Ob4=new MyTimer();
		for(int i=0; i<n2; i++)
			arr.contains(r.nextInt());
		Ob4.printTime("Поиск в массиве");
		}

	}

}
